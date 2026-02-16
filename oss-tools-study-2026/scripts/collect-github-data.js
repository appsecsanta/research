#!/usr/bin/env node
/**
 * Collect GitHub metrics for open-source AppSec tools.
 *
 * Reads: data/oss_tools_repos.json
 * Writes: data/oss_tools_github_raw.json
 *
 * Requires: GITHUB_TOKEN env var for 5000 req/hr rate limit.
 * Usage: GITHUB_TOKEN=xxx node scripts/collect-github-data.js
 */

const { Octokit } = require("@octokit/rest");
const fs = require("fs");
const path = require("path");

const INPUT = path.join(__dirname, "..", "data", "oss_tools_repos.json");
const OUTPUT = path.join(__dirname, "..", "data", "oss_tools_github_raw.json");

const token = process.env.GITHUB_TOKEN;
if (!token) {
  console.error("ERROR: Set GITHUB_TOKEN env var");
  process.exit(1);
}

const octokit = new Octokit({ auth: token });

// Delay between API calls to be polite
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

async function getRepoData(owner, repo) {
  try {
    const { data } = await octokit.repos.get({ owner, repo });
    return {
      stars: data.stargazers_count,
      forks: data.forks_count,
      watchers: data.subscribers_count,
      open_issues: data.open_issues_count,
      language: data.language,
      license: data.license?.spdx_id || null,
      created_at: data.created_at,
      updated_at: data.updated_at,
      pushed_at: data.pushed_at,
      archived: data.archived,
      description: data.description,
      topics: data.topics || [],
      default_branch: data.default_branch,
      size_kb: data.size,
    };
  } catch (e) {
    console.error(`  ERROR repo ${owner}/${repo}: ${e.message}`);
    return null;
  }
}

async function getContributorCount(owner, repo) {
  try {
    // Use per_page=1 and check the Link header for total count
    const res = await octokit.repos.listContributors({
      owner, repo, per_page: 1, anon: false,
    });
    const link = res.headers.link || "";
    const match = link.match(/page=(\d+)>; rel="last"/);
    return match ? parseInt(match[1]) : res.data.length;
  } catch (e) {
    return null;
  }
}

async function getCommitActivity(owner, repo) {
  try {
    // Last year of weekly commit activity
    const { data } = await octokit.repos.getCommitActivity({ owner, repo });
    if (!Array.isArray(data)) return null;
    const totalCommits = data.reduce((sum, w) => sum + w.total, 0);
    const last3months = data.slice(-13).reduce((sum, w) => sum + w.total, 0);
    const last1month = data.slice(-4).reduce((sum, w) => sum + w.total, 0);
    return {
      total_last_year: totalCommits,
      last_3_months: last3months,
      last_1_month: last1month,
      weekly_data: data.map((w) => ({ week: w.week, total: w.total })),
    };
  } catch (e) {
    return null;
  }
}

async function getReleases(owner, repo) {
  try {
    const { data } = await octokit.repos.listReleases({
      owner, repo, per_page: 30,
    });
    return {
      total_recent: data.length,
      latest: data[0]
        ? { tag: data[0].tag_name, date: data[0].published_at }
        : null,
      releases_last_year: data.filter((r) => {
        const d = new Date(r.published_at);
        const yearAgo = new Date();
        yearAgo.setFullYear(yearAgo.getFullYear() - 1);
        return d > yearAgo;
      }).length,
    };
  } catch (e) {
    return null;
  }
}

async function getIssueStats(owner, repo) {
  try {
    // Get recently closed issues to estimate response time
    const { data } = await octokit.issues.listForRepo({
      owner, repo, state: "closed", per_page: 30,
      sort: "updated", direction: "desc",
    });
    const issues = data.filter((i) => !i.pull_request);
    if (issues.length === 0) return { closed_sample: 0 };

    // Calculate average time to close (days)
    const closeTimes = issues.map((i) => {
      const created = new Date(i.created_at);
      const closed = new Date(i.closed_at);
      return (closed - created) / (1000 * 60 * 60 * 24);
    });
    const avgCloseTime = closeTimes.reduce((a, b) => a + b, 0) / closeTimes.length;
    const medianCloseTime = closeTimes.sort((a, b) => a - b)[Math.floor(closeTimes.length / 2)];

    return {
      closed_sample: issues.length,
      avg_close_days: Math.round(avgCloseTime * 10) / 10,
      median_close_days: Math.round(medianCloseTime * 10) / 10,
    };
  } catch (e) {
    return null;
  }
}

async function main() {
  const tools = JSON.parse(fs.readFileSync(INPUT, "utf-8"));
  const results = [];

  console.log(`Collecting GitHub data for ${tools.length} tools...`);

  for (let i = 0; i < tools.length; i++) {
    const tool = tools[i];
    const { owner, repo, slug, name, category } = tool;

    if (!repo) {
      console.log(`[${i + 1}/${tools.length}] SKIP ${name} (org-level URL, no specific repo)`);
      results.push({ ...tool, github: null, error: "org-level URL" });
      continue;
    }

    console.log(`[${i + 1}/${tools.length}] ${name} (${owner}/${repo})...`);

    const repoData = await getRepoData(owner, repo);
    await delay(200);

    const contributors = await getContributorCount(owner, repo);
    await delay(200);

    const commitActivity = await getCommitActivity(owner, repo);
    await delay(500); // This endpoint can be slow

    const releases = await getReleases(owner, repo);
    await delay(200);

    const issueStats = await getIssueStats(owner, repo);
    await delay(200);

    results.push({
      slug,
      name,
      category,
      license: tool.license,
      owner,
      repo,
      github: repoData
        ? {
            ...repoData,
            contributor_count: contributors,
            commit_activity: commitActivity,
            releases,
            issue_stats: issueStats,
          }
        : null,
    });

    // Rate limit awareness: ~6 API calls per tool, 200ms between each
    // 67 tools * 6 calls = ~400 calls, well within 5000/hr limit
  }

  // Save results
  const output = {
    metadata: {
      collected_at: new Date().toISOString(),
      tool_count: results.length,
      tools_with_data: results.filter((r) => r.github).length,
    },
    tools: results,
  };

  fs.writeFileSync(OUTPUT, JSON.stringify(output, null, 2) + "\n");
  console.log(`\nDone. Saved ${results.length} tools to ${OUTPUT}`);
  console.log(`  With data: ${output.metadata.tools_with_data}`);
  console.log(`  Failed: ${results.length - output.metadata.tools_with_data}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
