# Altoro Mutual — AltoroJ vulnerable banking application
# Multi-stage build: Gradle build → Tomcat 9 deployment

# Stage 1: Build the WAR
FROM gradle:7-jdk11 AS builder
RUN git clone https://github.com/HCL-TECH-SOFTWARE/AltoroJ.git /src
WORKDIR /src
RUN gradle build -x test

# Stage 2: Deploy to Tomcat
FROM tomcat:9-jdk11-temurin
RUN rm -rf /usr/local/tomcat/webapps/ROOT
COPY --from=builder /src/build/libs/altoromutual.war /usr/local/tomcat/webapps/ROOT.war
EXPOSE 8080
CMD ["catalina.sh", "run"]
