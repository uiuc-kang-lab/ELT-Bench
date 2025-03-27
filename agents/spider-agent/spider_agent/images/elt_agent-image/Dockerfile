FROM python:3.11

WORKDIR /workspace

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

RUN pip install pyarrow db-dtypes pandas numpy snowflake-connector-python openpyxl
# RUN pip install dbt-clickhouse
RUN pip install dbt-core
RUN pip install psycopg2-binary pymongo flask awscli localstack pandas

# # Install Meltano
# RUN pip install pipx && pipx ensurepath && pipx install meltano
# ENV PATH="/root/.local/bin:$PATH"

RUN pip install dbt-snowflake psycopg2-binary

RUN apt-get update && apt-get install -y \
    gnupg \
    software-properties-common \
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


# Set the default command to run when starting the container
CMD ["/bin/bash"]
