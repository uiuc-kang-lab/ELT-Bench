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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python packages
RUN pip install --upgrade pip

RUN pip install google-cloud-bigquery pyarrow db-dtypes pandas matplotlib scikit-learn seaborn numpy scipy statsmodels xgboost plotly tabulate snowflake-connector-python duckdb openpyxl
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
