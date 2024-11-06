import json
import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
codecommit_client = boto3.client('codecommit')
bucket_name = 'cdk-data-pipeline-center-test'
file_key = 'api-inventory-automation-script/repository-vitals.json'

def fetch_all_pull_requests(client, repository_name, status):
    pull_request_ids = []
    next_token = None
    while True:
        if next_token:
            response = client.list_pull_requests(
                repositoryName=repository_name,
                pullRequestStatus=status,
                nextToken=next_token
            )
        else:
            response = client.list_pull_requests(
                repositoryName=repository_name,
                pullRequestStatus=status
            )
        pull_request_ids.extend(response.get('pullRequestIds', []))
        next_token = response.get('nextToken')
        if not next_token:
            break
    return pull_request_ids

def get_pr_data_from_codecommit(repository_name, date):
    open_pr_ids = fetch_all_pull_requests(codecommit_client, repository_name, 'OPEN')
    closed_pr_ids = fetch_all_pull_requests(codecommit_client, repository_name, 'CLOSED')
    date_count = {"pr_count": 0, "pr_status": {"open": 0, "closed": 0, "merged": 0}}

    for pr_id in open_pr_ids + closed_pr_ids:
        pr_details = codecommit_client.get_pull_request(pullRequestId=pr_id)
        creation_datetime_utc = pr_details['pullRequest']['creationDate']
        creation_date_str = creation_datetime_utc.strftime('%Y-%m-%d')

        if creation_date_str == date.strftime('%Y-%m-%d'):
            if pr_id in open_pr_ids:
                date_count["pr_status"]["open"] += 1
            else:
                is_merged = pr_details['pullRequest']['pullRequestTargets'][0].get('mergeMetadata', {}).get('isMerged', False)
                if is_merged:
                    date_count["pr_status"]["merged"] += 1
                else:
                    date_count["pr_status"]["closed"] += 1
            date_count["pr_count"] += 1

    return {"date": date.strftime('%Y-%m-%d'), "pr_count": date_count["pr_count"], "pr_status": date_count["pr_status"]}

def lambda_handler(event, context):
    query_params = event.get('queryStringParameters', {})
    repository_name = query_params.get('repository-name', 'cdx-android-app')
    end_date_default = datetime.now().date()
    start_date_default = end_date_default - timedelta(days=30)
    start_date_str = query_params.get('start-date', start_date_default.strftime('%Y-%m-%d'))
    end_date_str = query_params.get('end-date', end_date_default.strftime('%Y-%m-%d'))

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_content = response['Body'].read().decode('utf-8')
        data = json.loads(file_content)
        
        repo_data_entry = next((repo for repo in data if repo['repository_name'] == repository_name), None)
        if repo_data_entry is None:
            repo_data_entry = {"repository_name": repository_name, "data": []}
            data.append(repo_data_entry)

        # Find the last date in the JSON data for this repository
        if repo_data_entry['data']:
            last_date_in_json = max(datetime.strptime(entry['date'], '%Y-%m-%d').date() for entry in repo_data_entry['data'])
        else:
            last_date_in_json = start_date

        # Ensure all dates from the last entry up to today are populated
        pr_data = []
        total_open = 0
        total_closed = 0
        total_merged = 0

        for n in range((end_date - start_date).days + 1):
            current_date = start_date + timedelta(days=n)
            current_date_str = current_date.strftime('%Y-%m-%d')

            # Check if date exists in JSON
            existing_entry = next((entry for entry in repo_data_entry['data'] if entry['date'] == current_date_str), None)
            if existing_entry:
                pr_data.append({
                    "date": current_date_str,
                    "pr_count": existing_entry["pr_count"]
                })
                total_open += existing_entry["pr_status"]["open"]
                total_closed += existing_entry["pr_status"]["closed"]
                total_merged += existing_entry["pr_status"]["merged"]
            else:
                # Only fetch data from CodeCommit for dates up to today (not future dates)
                if current_date <= end_date_default:
                    new_data = get_pr_data_from_codecommit(repository_name, current_date)
                    pr_data.append({
                        "date": current_date_str,
                        "pr_count": new_data["pr_count"]
                    })
                    total_open += new_data["pr_status"]["open"]
                    total_closed += new_data["pr_status"]["closed"]
                    total_merged += new_data["pr_status"]["merged"]
                    # Append new data only for non-future dates
                    repo_data_entry['data'].append(new_data)

        # Sort and write back to S3 only if new data was added
        repo_data_entry['data'].sort(key=lambda x: x['date'])
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=json.dumps(data)
        )

        # Prepare the response data
        total_pr_count = total_open + total_closed + total_merged
        result = {
            "repository_name": repository_name,
            "pr_data": pr_data,
            "pr_status": {
                "open": total_open,
                "closed": total_closed,
                "merged": total_merged
            },
            "pr_status_percentage": {
                "open_percentage": round((total_open / total_pr_count) * 100, 2) if total_pr_count else 0.0,
                "closed_percentage": round((total_closed / total_pr_count) * 100, 2) if total_pr_count else 0.0,
                "merged_percentage": round((total_merged / total_pr_count) * 100, 2) if total_pr_count else 0.0
            }
        }

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps(result)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }