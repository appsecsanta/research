# Altoro Mutual — AltoroJ vulnerable banking application
# Based on the OWASP AltoroJ project (Tomcat + Java)
FROM tomcat:9-jdk17

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# TODO: Download or copy AltoroJ WAR into webapps/
# For now this is a placeholder — the WAR will be added in a later task.

EXPOSE 8080
CMD ["catalina.sh", "run"]
