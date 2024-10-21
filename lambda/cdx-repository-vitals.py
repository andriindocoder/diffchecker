import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

codecommit_client = boto3.client('codecommit')

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

def lambda_handler(event, context):
    query_params = event.get('queryStringParameters', {})
    repository_name = query_params.get('repository-name', 'cdx-mf-financing-core')
    start_date_str = query_params.get('start-date', '2024-08-01')
    end_date_str = query_params.get('end-date', '2024-08-10')

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

        if end_date < start_date:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',  # CORS header
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({"error": "end-date cannot be before start-date"})
            }

        pr_data = {}
        total_open = 0
        total_closed = 0
        total_merged = 0

        open_pr_ids = fetch_all_pull_requests(codecommit_client, repository_name, 'OPEN')
        closed_pr_ids = fetch_all_pull_requests(codecommit_client, repository_name, 'CLOSED')

        for pr_id in open_pr_ids:
            pr_details = codecommit_client.get_pull_request(pullRequestId=pr_id)
            creation_date = pr_details['pullRequest']['creationDate']
            creation_date = datetime.strptime(creation_date.isoformat(), "%Y-%m-%dT%H:%M:%S.%f%z")
            creation_date_only = creation_date.date()

            if start_date.date() <= creation_date_only <= end_date.date():
                total_open += 1
                pr_data[creation_date_only.isoformat()] = pr_data.get(creation_date_only.isoformat(), 0) + 1

        for pr_id in closed_pr_ids:
            pr_details = codecommit_client.get_pull_request(pullRequestId=pr_id)
            creation_date = pr_details['pullRequest']['creationDate']
            creation_date = datetime.strptime(creation_date.isoformat(), "%Y-%m-%dT%H:%M:%S.%f%z")
            creation_date_only = creation_date.date()

            if start_date.date() <= creation_date_only <= end_date.date():
                merge_metadata = pr_details['pullRequest']['pullRequestTargets'][0].get('mergeMetadata', {})
                is_merged = merge_metadata.get('isMerged', False)

                if is_merged:
                    total_merged += 1
                else:
                    total_closed += 1

                pr_data[creation_date_only.isoformat()] = pr_data.get(creation_date_only.isoformat(), 0) + 1

        total_pull_requests = total_open + total_closed + total_merged
        if total_pull_requests > 0:
            open_percentage = (total_open / total_pull_requests) * 100
            closed_percentage = (total_closed / total_pull_requests) * 100
            merged_percentage = (total_merged / total_pull_requests) * 100
        else:
            open_percentage = 0.0
            closed_percentage = 0.0
            merged_percentage = 0.0

        days_in_range = (end_date - start_date).days + 1

        pr_data_by_day = []
        for day in range(days_in_range):
            current_date = (start_date + timedelta(days=day)).date().isoformat() + "T00:00:00"
            pr_data_by_day.append({
                "date": current_date,
                "pr_count": pr_data.get(current_date[:10], 0)  # Only compare YYYY-MM-DD part
            })

        pr_status = {
            "open": total_open,
            "closed": total_closed,
            "merged": total_merged
        }

        pr_status_percentage = {
            "open_percentage": round(open_percentage, 2),
            "closed_percentage": round(closed_percentage, 2),
            "merged_percentage": round(merged_percentage, 2)
        }

        result = {
            "repository_name": repository_name,
            "pr_data": pr_data_by_day,
            "pr_status": pr_status,
            "pr_status_percentage": pr_status_percentage
        }

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',  # CORS header
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(result, default=str)
        }

    except ClientError as e:
        if e.response['Error']['Code'] == 'RepositoryDoesNotExistException':
            return {
                'statusCode': 404,
                'headers': {
                    'Access-Control-Allow-Origin': '*',  # CORS header
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({
                    'error': 'Repository not found',
                    'repository_name': repository_name
                })
            }
        else:
            return {
                'statusCode': 500,
                'headers': {
                    'Access-Control-Allow-Origin': '*',  # CORS header
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps(f"Error: {e.response['Error']['Message']}")
            }