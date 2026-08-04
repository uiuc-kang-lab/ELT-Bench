FROM python:3.12

# Update and install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    iputils-ping \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python packages
RUN pip install --upgrade pip

RUN pip install pyarrow db-dtypes pandas numpy plotly snowflake-connector-python openpyxl
# RUN pip install dbt-clickhouse
RUN pip install dbt-core
RUN pip install psycopg2-binary pymongo flask awscli localstack pandas

# # Install Meltano
# RUN pip install pipx && pipx ensurepath && pipx install meltano
# ENV PATH="/root/.local/bin:$PATH"

RUN pip install \
    dbt-snowflake \
    dbt-databricks \
    dbt-redshift \
    databricks-sdk \
    databricks-sql-connector \
    redshift-connector \
    psycopg2-binary

# OpenHands agent stack — runs the agent and its tools (file_editor / terminal /
# grep / glob) inside this container, sandboxed to /workspace by the bind-mount.
RUN pip install --no-cache-dir \
        openhands-sdk==1.19.1 \
        openhands-tools==1.19.1 \
        openhands-agent-server==1.19.1

RUN apt-get update && apt-get install -y \
    gnupg \
    wget \
    lsb-release

# Add HashiCorp GPG key
RUN wget -O- https://apt.releases.hashicorp.com/gpg | \
    gpg --dearmor | \
    tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null

# Add HashiCorp repository to the list of APT sources
RUN echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
    https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    tee /etc/apt/sources.list.d/hashicorp.list

# Update package list and install Terraform
RUN apt-get update && apt-get install -y terraform

WORKDIR /

# Set the default command to run when starting the container
CMD ["/bin/bash"]
