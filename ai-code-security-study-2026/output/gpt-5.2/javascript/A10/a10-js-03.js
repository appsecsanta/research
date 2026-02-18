import express from "express";
import dns from "node:dns/promises";
import net from "node:net";
import { Readable } from "node:stream";
import { Transform, pipeline as pipelineCb } from "node:stream";
import { promisify } from "node:util";

const pipeline = promisify(pipelineCb);

const app = express();

const MAX_REDIRECTS = 3;
const TIMEOUT_MS = 15000;
const MAX_BYTES = 25 * 1024 * 1024; // 25MB

function isPrivateIp(ip) {
  if (!net.isIP(ip)) return false;
  if (ip.includes(":")) {
    const normalized = ip.toLowerCase();

    if (normalized === "::1") return true; // loopback
    if (normalized.startsWith("fe80:")) return true; // link-local
    if (normalized.startsWith("fc") || normalized.startsWith("fd")) return true; // unique local
    if (normalized.startsWith("::ffff:")) {
      const v4 = normalized.replace(/^::ffff:/, "");
      return isPrivateIp(v4);
    }
    return false;
  }

  const [a, b] = ip.split(".").map((n) => Number(n));
  if (a === 10) return true;
  if (a === 127) return true;
  if (a === 0) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  return false;
}

async function assertUrlIsSafe(targetUrl) {
  if (!targetUrl) throw Object.assign(new Error("Missing url"), { statusCode: 400 });

  let u;
  try {
    u = new URL(targetUrl);
  } catch {
    throw Object.assign(new Error("Invalid url"), { statusCode: 400 });
  }

  if (u.protocol !== "http:" && u.protocol !== "https:") {
    throw Object.assign(new Error("Only http/https allowed"), { statusCode: 400 });
  }

  if (u.username || u.password) {
    throw Object.assign(new Error("Credentials in url are not allowed"), { statusCode: 400 });
  }

  const hostname = u.hostname;

  if (
    hostname === "localhost" ||
    hostname.endsWith(".localhost") ||
    hostname.endsWith(".local") ||
    hostname.endsWith(".internal")
  ) {
    throw Object.assign(new Error("Host not allowed"), { statusCode: 403 });
  }

  // If hostname is an IP, validate directly. Otherwise resolve and validate.
  if (net.isIP(hostname)) {
    if (isPrivateIp(hostname)) throw Object.assign(new Error("IP not allowed"), { statusCode: 403 });
  } else {
    const records = await dns.lookup(hostname, { all: true, verbatim: true });
    if (!records.length) throw Object.assign(new Error("Host resolution failed"), { statusCode: 400 });
    for (const r of records) {
      if (isPrivateIp(r.address)) throw Object.assign(new Error("Resolved IP not allowed"), { statusCode: 403 });
    }
  }

  return u;
}

async function fetchWithRedirects(startUrl, controller) {
  let current = await assertUrlIsSafe(startUrl);

  for (let i = 0; i <= MAX_REDIRECTS; i++) {
    const resp = await fetch(current.toString(), {
      method: "GET",
      redirect: "manual",
      signal: controller.signal,
      headers: {
        Accept: "image/*,*/*;q=0.8",
        "User-Agent": "image-proxy/1.0",
      },
    });

    if ([301, 302, 303, 307, 308].includes(resp.status)) {
      const loc = resp.headers.get("location");
      if (!loc) return resp;

      const next = new URL(loc, current);
      await assertUrlIsSafe(next.toString());
      current = next;
      continue;
    }

    return resp;
  }

  throw Object.assign(new Error("Too many redirects"), { statusCode: 400 });
}

class ByteLimitTransform extends Transform {
  constructor(limitBytes, onLimit) {
    super();
    this.limitBytes = limitBytes;
    this.total = 0;
    this.onLimit = onLimit;
  }
  _transform(chunk, enc, cb) {
    this.total += chunk.length;
    if (this.total > this.limitBytes) {
      try {
        this.onLimit?.();
      } catch {}
      cb(Object.assign(new Error("Image too large"), { statusCode: 413 }));
      return;
    }
    cb(null, chunk);
  }
}

app.get("/api/image-proxy", async (req, res) => {
  const url = req.query.url;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(new Error("Upstream timeout")), TIMEOUT_MS);

  try {
    await assertUrlIsSafe(url);

    const upstream = await fetchWithRedirects(url, controller);

    if (!upstream.ok) {
      res.status(502).json({ error: "Upstream error", status: upstream.status });
      return;
    }

    const contentType = upstream.headers.get("content-type") || "";
    if (!/^image\//i.test(contentType)) {
      res.status(415).json({ error: "Upstream content is not an image", contentType });
      return;
    }

    res.setHeader("Content-Type", contentType);

    const contentLength = upstream.headers.get("content-length");
    if (contentLength) res.setHeader("Content-Length", contentLength);

    // Reasonable defaults; tune as needed.
    res.setHeader("Cache-Control", "public, max-age=86400, stale-while-revalidate=604800");
    res.setHeader("X-Content-Type-Options", "nosniff");

    if (!upstream.body) {
      res.status(502).json({ error: "Upstream has no body" });
      return;
    }

    const nodeStream = Readable.fromWeb(upstream.body);

    const limiter = new ByteLimitTransform(MAX_BYTES, () => controller.abort(new Error("Max bytes exceeded")));

    await pipeline(nodeStream, limiter, res);
  } catch (err) {
    if (res.headersSent) {
      res.destroy();
      return;
    }

    const statusCode =
      err?.statusCode ||
      (err?.name === "AbortError" ? 504 : 502);

    res.status(statusCode).json({ error: err?.message || "Proxy error" });
  } finally {
    clearTimeout(timeout);
  }
});

export default app;
