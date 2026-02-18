#
# Python Web Application Dependencies
#
# This file is used by pip to install the exact versions of packages required
# for the application, ensuring reproducible builds.
#
# To install, run: pip install -r requirements.txt
#

# -- Core Web Framework & WSGI Server --
Flask==2.3.3
gunicorn==21.2.0

# -- Database ORM (PostgreSQL example) --
SQLAlchemy==2.0.23
Flask-SQLAlchemy==3.1.1
psycopg2-binary==2.9.9

# -- User Authentication, Sessions & Forms --
Flask-Login==0.6.3
Flask-WTF==1.2.1
bcrypt==4.1.2
WTForms==3.1.1

# -- Image Processing --
Pillow==10.1.0

# -- XML Parsing --
lxml==4.9.3

# -- Utilities --
python-dotenv==1.0.0

# -- Transitive Dependencies --
# These are dependencies of the packages listed above. They are pinned here
# to ensure the entire dependency tree is locked.
blinker==1.7.0
cffi==1.16.0
click==8.1.7
itsdangerous==2.1.2
Jinja2==3.1.2
MarkupSafe==2.1.3
pycparser==2.21
Werkzeug==3.0.1
