# Trigger a sync

```
curl --request POST \
     --url http://<airbyte-server>/api/public/v1/jobs \
     --header 'accept: application/json' \
     -u '<username>:password' \
     --header 'content-type: application/json' \
     --data '
{
  "jobType": "sync",
  "connectionId": "<connection_id>"
}
'
```