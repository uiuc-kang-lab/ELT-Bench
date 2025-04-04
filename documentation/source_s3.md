---
# generated by https://github.com/hashicorp/terraform-plugin-docs
page_title: "airbyte_source_s3 Resource - terraform-provider-airbyte"
subcategory: ""
description: |-
  SourceS3 Resource
---

# airbyte_source_s3 (Resource)

SourceS3 Resource

## Example Usage

```terraform
resource "airbyte_source_s3" "my_source_s3" {
  configuration = {
    aws_access_key_id     = "...my_aws_access_key_id..."
    aws_secret_access_key = "...my_aws_secret_access_key..."
    bucket                = "...my_bucket..."
    endpoint              = "https://my-s3-endpoint.com"
    region_name           = "...my_region_name..."
    role_arn              = "...my_role_arn..."
    start_date            = "2021-01-01T00:00:00.000000Z"
    streams = [
      {
        days_to_sync_if_history_is_full = 6
        format = {
          avro_format = {
            double_as_string = true
          }
        }
        globs = [
          "...",
        ]
        input_schema                                = "...my_input_schema..."
        name                                        = "Christie Emard"
        recent_n_files_to_read_for_schema_discovery = 3
        schemaless                                  = true
        validation_policy                           = "Emit Record"
      },
    ]
  }
  definition_id = "819ff393-429d-4316-9dd8-595e9c61e20d"
  name          = "Pedro West"
  secret_id     = "...my_secret_id..."
  workspace_id  = "b11c60c3-a7ba-4336-a48b-e45dfad9324f"
}
```

<!-- schema generated by tfplugindocs -->
## Schema

### Required

- `configuration` (Attributes) NOTE: When this Spec is changed, legacy_config_transformer.py must also be modified to uptake the changes
because it is responsible for converting legacy S3 v3 configs into v4 configs using the File-Based CDK. (see [below for nested schema](#nestedatt--configuration))
- `name` (String) Name of the source e.g. dev-mysql-instance.
- `workspace_id` (String)

### Optional

- `definition_id` (String) The UUID of the connector definition. One of configuration.sourceType or definitionId must be provided. Requires replacement if changed.
- `secret_id` (String) Optional secretID obtained through the public API OAuth redirect flow. Requires replacement if changed.

### Read-Only

- `source_id` (String)
- `source_type` (String)

<a id="nestedatt--configuration"></a>
### Nested Schema for `configuration`

Required:

- `bucket` (String) Name of the S3 bucket where the file(s) exist.
- `streams` (Attributes List) Each instance of this configuration defines a <a href="https://docs.airbyte.com/cloud/core-concepts#stream">stream</a>. Use this to define which files belong in the stream, their format, and how they should be parsed and validated. When sending data to warehouse destination such as Snowflake or BigQuery, each stream is a separate table. (see [below for nested schema](#nestedatt--configuration--streams))

Optional:

- `aws_access_key_id` (String, Sensitive) In order to access private Buckets stored on AWS S3, this connector requires credentials with the proper permissions. If accessing publicly available data, this field is not necessary.
- `aws_secret_access_key` (String, Sensitive) In order to access private Buckets stored on AWS S3, this connector requires credentials with the proper permissions. If accessing publicly available data, this field is not necessary.
- `endpoint` (String) Endpoint to an S3 compatible service. Leave empty to use AWS. Default: ""
- `region_name` (String) AWS region where the S3 bucket is located. If not provided, the region will be determined automatically.
- `role_arn` (String) Specifies the Amazon Resource Name (ARN) of an IAM role that you want to use to perform operations requested using this profile. Set the External ID to the Airbyte workspace ID, which can be found in the URL of this page.
- `start_date` (String) UTC date and time in the format 2017-01-25T00:00:00.000000Z. Any file modified before this date will not be replicated.

<a id="nestedatt--configuration--streams"></a>
### Nested Schema for `configuration.streams`

Required:

- `format` (Attributes) The configuration options that are used to alter how to read incoming files that deviate from the standard formatting. (see [below for nested schema](#nestedatt--configuration--streams--format))
- `name` (String) The name of the stream.

- `globs` (List of String) The pattern used to specify which files should be selected from the file system. For more information on glob pattern matching look <a href="https://en.wikipedia.org/wiki/Glob_(programming)">here</a>. \(tl;dr -&gt; path pattern syntax using [wcmatch.glob](https://facelessuser.github.io/wcmatch/glob/). GLOBSTAR and SPLIT flags are enabled.\)

  This connector can sync multiple files by using glob-style patterns, rather than requiring a specific path for every file. This enables:

  - Referencing many files with just one pattern, e.g. `**` would indicate every file in the bucket.
  - Referencing future files that don't exist yet \(and therefore don't have a specific path\).

  You must provide a path pattern. You can also provide many patterns split with \| for more complex directory layouts.

  Each path pattern is a reference from the _root_ of the bucket, so don't include the bucket name in the pattern\(s\).

  Some example patterns:

  - `**` : match everything.
  - `**/*.csv` : match all files with specific extension.
  - `myFolder/**/*.csv` : match all csv files anywhere under myFolder.
  - `*/**` : match everything at least one folder deep.
  - `*/*/*/**` : match everything at least three folders deep.
  - `**/file.*|**/file` : match every file called "file" with any extension \(or no extension\).
  - `x/*/y/*` : match all files that sit in folder x -&gt; any folder -&gt; folder y.
  - `**/prefix*.csv` : match all csv files with specific prefix.
  - `**/prefix*.parquet` : match all parquet files with specific prefix.

  Let's look at a specific example, matching the following bucket layout:

  ```text
  myBucket
      -> log_files
      -> some_table_files
          -> part1.csv
          -> part2.csv
      -> images
      -> more_table_files
          -> part3.csv
      -> extras
          -> misc
              -> another_part1.csv
  ```

  We want to pick up part1.csv, part2.csv and part3.csv \(excluding another_part1.csv for now\). We could do this a few different ways:

  - We could pick up every csv file called "partX" with the single pattern `**/part*.csv`.
  - To be a bit more robust, we could use the dual pattern `some_table_files/*.csv|more_table_files/*.csv` to pick up relevant files only from those exact folders.
  - We could achieve the above in a single pattern by using the pattern `*table_files/*.csv`. This could however cause problems in the future if new unexpected folders started being created.
  - We can also recursively wildcard, so adding the pattern `extras/**/*.csv` would pick up any csv files nested in folders below "extras", such as "extras/misc/another_part1.csv".

  As you can probably tell, there are many ways to achieve the same goal with path patterns. We recommend using a pattern that ensures clarity and is robust against future additions to the directory structure.

Optional:

- `days_to_sync_if_history_is_full` (Number) When the state history of the file store is full, syncs will only read files that were last modified in the provided day range. Default: 3

- `input_schema` (String) The schema that will be used to validate records extracted from the file. This will override the stream schema that is auto-detected from incoming files.
- `recent_n_files_to_read_for_schema_discovery` (Number) The number of resent files which will be used to discover the schema for this stream.
- `schemaless` (Boolean) When enabled, syncs will not validate or structure records against the stream's schema. Default: false
- `validation_policy` (String) The name of the validation policy that dictates sync behavior when a record does not adhere to the stream schema. must be one of ["Emit Record", "Skip Record", "Wait for Discover"]; Default: "Emit Record"

<a id="nestedatt--configuration--streams--format"></a>
### Nested Schema for `configuration.streams.format`

Optional:

- `avro_format` (Attributes) (see [below for nested schema](#nestedatt--configuration--streams--format--avro_format))
- `csv_format` (Attributes) (see [below for nested schema](#nestedatt--configuration--streams--format--csv_format))
- `jsonl_format` (Attributes) (see [below for nested schema](#nestedatt--configuration--streams--format--jsonl_format))
- `parquet_format` (Attributes) (see [below for nested schema](#nestedatt--configuration--streams--format--parquet_format))
- `unstructured_document_format` (Attributes) Extract text from document formats (.pdf, .docx, .md, .pptx) and emit as one record per file. (see [below for nested schema](#nestedatt--configuration--streams--format--unstructured_document_format))

<a id="nestedatt--configuration--streams--format--avro_format"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format`

Optional:

- `double_as_string` (Boolean) Whether to convert double fields to strings. This is recommended if you have decimal numbers with a high degree of precision because there can be a loss precision when handling floating point numbers. Default: false


<a id="nestedatt--configuration--streams--format--csv_format"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format`

Optional:

- `delimiter` (String) The character delimiting individual cells in the CSV data. This may only be a 1-character string. For tab-delimited data enter '\t'. Default: ","
- `double_quote` (Boolean) Whether two quotes in a quoted CSV value denote a single quote in the data. Default: true
- `encoding` (String) The character encoding of the CSV data. Leave blank to default to <strong>UTF8</strong>. See <a href="https://docs.python.org/3/library/codecs.html#standard-encodings" target="_blank">list of python encodings</a> for allowable options. Default: "utf8"
- `escape_char` (String) The character used for escaping special characters. To disallow escaping, leave this field blank.
- `false_values` (List of String) A set of case-sensitive strings that should be interpreted as false values.
- `header_definition` (Attributes) How headers will be defined. `User Provided` assumes the CSV does not have a header row and uses the headers provided and `Autogenerated` assumes the CSV does not have a header row and the CDK will generate headers using for `f{i}` where `i` is the index starting from 0. Else, the default behavior is to use the header from the CSV file. If a user wants to autogenerate or provide column names for a CSV having headers, they can skip rows. (see [below for nested schema](#nestedatt--configuration--streams--format--unstructured_document_format--header_definition))
- `ignore_errors_on_fields_mismatch` (Boolean) Whether to ignore errors that occur when the number of fields in the CSV does not match the number of columns in the schema. Default: false
- `null_values` (List of String) A set of case-sensitive strings that should be interpreted as null values. For example, if the value 'NA' should be interpreted as null, enter 'NA' in this field.
- `quote_char` (String) The character used for quoting CSV values. To disallow quoting, make this field blank. Default: "\""
- `skip_rows_after_header` (Number) The number of rows to skip after the header row. Default: 0
- `skip_rows_before_header` (Number) The number of rows to skip before the header row. For example, if the header row is on the 3rd row, enter 2 in this field. Default: 0
- `strings_can_be_null` (Boolean) Whether strings can be interpreted as null values. If true, strings that match the null_values set will be interpreted as null. If false, strings that match the null_values set will be interpreted as the string itself. Default: true
- `true_values` (List of String) A set of case-sensitive strings that should be interpreted as true values.

<a id="nestedatt--configuration--streams--format--unstructured_document_format--header_definition"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format.header_definition`

Optional:

- `autogenerated` (Attributes) (see [below for nested schema](#nestedatt--configuration--streams--format--unstructured_document_format--header_definition--autogenerated))
- `from_csv` (Attributes) (see [below for nested schema](#nestedatt--configuration--streams--format--unstructured_document_format--header_definition--from_csv))
- `user_provided` (Attributes) (see [below for nested schema](#nestedatt--configuration--streams--format--unstructured_document_format--header_definition--user_provided))

<a id="nestedatt--configuration--streams--format--unstructured_document_format--header_definition--autogenerated"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format.header_definition.user_provided`


<a id="nestedatt--configuration--streams--format--unstructured_document_format--header_definition--from_csv"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format.header_definition.user_provided`


<a id="nestedatt--configuration--streams--format--unstructured_document_format--header_definition--user_provided"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format.header_definition.user_provided`

Required:

- `column_names` (List of String) The column names that will be used while emitting the CSV records




<a id="nestedatt--configuration--streams--format--jsonl_format"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format`


<a id="nestedatt--configuration--streams--format--parquet_format"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format`

Optional:

- `decimal_as_float` (Boolean) Whether to convert decimal fields to floats. There is a loss of precision when converting decimals to floats, so this is not recommended. Default: false


<a id="nestedatt--configuration--streams--format--unstructured_document_format"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format`

Optional:

- `processing` (Attributes) Processing configuration (see [below for nested schema](#nestedatt--configuration--streams--format--unstructured_document_format--processing))
- `skip_unprocessable_files` (Boolean) If true, skip files that cannot be parsed and pass the error message along as the _ab_source_file_parse_error field. If false, fail the sync. Default: true
- `strategy` (String) The strategy used to parse documents. `fast` extracts text directly from the document which doesn't work for all files. `ocr_only` is more reliable, but slower. `hi_res` is the most reliable, but requires an API key and a hosted instance of unstructured and can't be used with local mode. See the unstructured.io documentation for more details: https://unstructured-io.github.io/unstructured/core/partition.html#partition-pdf. must be one of ["auto", "fast", "ocr_only", "hi_res"]; Default: "auto"

<a id="nestedatt--configuration--streams--format--unstructured_document_format--processing"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format.processing`

Optional:

- `local` (Attributes) Process files locally, supporting `fast` and `ocr` modes. This is the default option. (see [below for nested schema](#nestedatt--configuration--streams--format--unstructured_document_format--processing--local))

<a id="nestedatt--configuration--streams--format--unstructured_document_format--processing--local"></a>
### Nested Schema for `configuration.streams.format.unstructured_document_format.processing.local`

## Import

Import is supported using the following syntax:

```shell
terraform import airbyte_source_s3.my_airbyte_source_s3 ""
```
