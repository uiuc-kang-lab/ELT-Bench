# Build from the repository root:
# docker build --build-arg BASE_IMAGE=elt-swe-openhands \
#   -f agents/common/offline-deps.Dockerfile \
#   -t elt-swe-openhands:offline agents/common
# Network access is needed only while building this dependency layer.
ARG BASE_IMAGE=elt-swe-openhands
FROM ${BASE_IMAGE} AS offline_dependencies

USER root
COPY offline-deps/main.tf /tmp/elt-offline-build/main.tf
COPY offline-deps/terraform.rc /opt/elt/terraform.rc

# Use the provider version required by all 100 supplied task configurations.
# providers mirror selects the platform on which Terraform runs during build.
# Ignore any inherited runtime mirror configuration during this trusted build.
RUN mkdir -p /opt/elt/terraform-providers && \
    TF_CLI_CONFIG_FILE=/dev/null terraform -chdir=/tmp/elt-offline-build \
      providers mirror /opt/elt/terraform-providers

# A fixed version of the generic dbt-utils macros, not task-specific models.
# Runtime packages.yml can use: packages: [{local: /opt/elt/dbt_utils}]
RUN python - <<'PY'
import hashlib
import io
import pathlib
import tarfile
import urllib.request

version = "1.3.0"
url = f"https://github.com/dbt-labs/dbt-utils/archive/refs/tags/{version}.tar.gz"
limit = 20 * 1024 * 1024
with urllib.request.urlopen(url, timeout=120) as response:
    data = response.read(limit + 1)
if len(data) > limit:
    raise RuntimeError("dbt-utils archive exceeds the build download limit")

destination = pathlib.Path("/opt/elt/dbt_utils")
destination.mkdir(parents=True)
prefix = f"dbt-utils-{version}"
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
    for member in archive:
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != prefix:
            raise RuntimeError("unexpected path in dbt-utils archive")
        relative = path.parts[1:]
        if not relative:
            if not member.isdir():
                raise RuntimeError("invalid archive root")
            continue
        target = destination.joinpath(*relative)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("wb") as output:
                while chunk := source.read(65536):
                    output.write(chunk)
        else:
            # Do not extract symlinks, hardlinks, devices or FIFOs into the image.
            raise RuntimeError("unsupported entry in dbt-utils archive")

if not (destination / "dbt_project.yml").is_file():
    raise RuntimeError("dbt-utils project is missing")
(destination / ".archive-sha256").write_text(hashlib.sha256(data).hexdigest() + "\n")
PY

RUN find /opt/elt/terraform-providers /opt/elt/dbt_utils -type f -exec chmod 0444 {} + && \
    find /opt/elt/terraform-providers /opt/elt/dbt_utils -type d -exec chmod 0555 {} + && \
    chmod 0444 /opt/elt/terraform.rc

# Preserve the base image's user, entrypoint, workdir and preinstalled tools.
FROM ${BASE_IMAGE}
COPY --from=offline_dependencies /opt/elt/terraform-providers /opt/elt/terraform-providers
COPY --from=offline_dependencies /opt/elt/dbt_utils /opt/elt/dbt_utils
COPY --from=offline_dependencies /opt/elt/terraform.rc /opt/elt/terraform.rc
ENV TF_CLI_CONFIG_FILE=/opt/elt/terraform.rc \
    CHECKPOINT_DISABLE=1
