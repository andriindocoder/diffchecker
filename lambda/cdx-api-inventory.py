import json
import boto3
from datetime import datetime
from botocore.exceptions import ClientError

# Initialize AWS clients
s3 = boto3.client('s3')
codebuild = boto3.client('codebuild')
codepipeline = boto3.client('codepipeline')
codecommit = boto3.client('codecommit', region_name='ap-southeast-1')

bucket_name = 'beu-api-inventory-web'
file_key = 'catalogue-counter.txt'  # The file path in S3

def get_codecommit_tags(repository_name):
    """Retrieve the tags for a given CodeCommit repository."""
    try:
        response = codecommit.list_tags_for_resource(
            resourceArn=f'arn:aws:codecommit:ap-southeast-1:482680362026:{repository_name}'
        )
        tags = response.get('tags', {})
        return {
            'repository_owner': tags.get('Project', None),  # Use None if tag is not found
            'repository_domain': tags.get('Domain', None),
            'repository_subdomain': tags.get('Sub-Domain', None)
        }
    except ClientError as e:
        print(f"Error retrieving tags for repository {repository_name}: {e}")
        return {
            'repository_owner': None,
            'repository_domain': None,
            'repository_subdomain': None
        }

def get_existing_catalogue(bucket_name, file_key):
    """Retrieve the existing catalogue-counter.txt file from S3 if it exists."""
    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        existing_data = response['Body'].read().decode('utf-8')
        return json.loads(existing_data)  # Load the existing JSON content
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return []  # Return empty list if file does not exist
        else:
            raise e

def update_catalogue_for_repository(repository_name, bucket_name, file_key):
    """Update a specific repository entry in the catalogue-counter.txt in S3."""
    # Fetch the existing catalogue from S3
    existing_catalogue = get_existing_catalogue(bucket_name, file_key)

    # Get CodeCommit tags for the repository
    repository_tags = get_codecommit_tags(repository_name)
    
    # Set the trigger date to now
    trigger_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    updated_catalogue = []
    repository_found = False
    
    # Iterate through the existing catalogue to update the matching repository
    for entry in existing_catalogue:
        if entry['repository_name'] == repository_name:
            # Update the repository entry
            entry.update({
                'status': True,  # JSON `true`
                'trigger_date': trigger_date,
                'repository_owner': repository_tags['repository_owner'],
                'repository_domain': repository_tags['repository_domain'],
                'repository_subdomain': repository_tags['repository_subdomain']
            })
            repository_found = True
        updated_catalogue.append(entry)
    
    # If the repository is not found in the existing catalogue, add it as a new entry
    if not repository_found:
        api_inventory_url = f"http://api.cicd.cdx-bankislam.com/beu-api-inventory-web/{repository_name}/index.html"
        updated_catalogue.append({
            'repository_name': repository_name,
            'api_inventory_url': api_inventory_url,
            'trigger_date': trigger_date,
            'status': True,  # JSON `true`
            'repository_owner': repository_tags['repository_owner'],
            'repository_domain': repository_tags['repository_domain'],
            'repository_subdomain': repository_tags['repository_subdomain']
        })

    # Upload the updated catalogue back to S3
    s3.put_object(
        Bucket=bucket_name, 
        Key=file_key, 
        Body=json.dumps(updated_catalogue, indent=4),
        ContentType='application/json'
    )
    
    return updated_catalogue

def lambda_handler(event, context):
    try:
        # Determine if the trigger is from CodePipeline or Direct Invocation
        if 'CodePipeline.job' in event:
            print("Triggered by CodePipeline")
            job_id = event['CodePipeline.job']['id']
            user_parameters = json.loads(event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters'])
            repository_name = user_parameters.get('repository-name')
            report_to_codepipeline = True
        else:
            print("Triggered by Test Event or Direct Invocation")
            repository_name = event.get('repository-name')
            job_id = None
            report_to_codepipeline = False

        if not repository_name:
            raise ValueError("Error: 'repository-name' is required")

        # Update the repository in the catalogue
        updated_catalogue = update_catalogue_for_repository(repository_name, bucket_name, file_key)
        print(f"Updated catalogue: {updated_catalogue}")

        # Start the CodeBuild project (assuming this is required)
        response = codebuild.start_build(
            projectName='cb-cdx-mf-api-inventory',
            environmentVariablesOverride=[
                {'name': 'REPOSITORY_NAME', 'value': repository_name, 'type': 'PLAINTEXT'}
            ]
        )

        # Report success to CodePipeline if applicable
        if report_to_codepipeline:
            codepipeline.put_job_success_result(jobId=job_id)
            print("Successfully reported to CodePipeline")

        # Return success response with CORS headers
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({
                'message': 'Build started successfully!',
                'build_id': response['build']['id']
            })
        }

    except Exception as e:
        print(f"Function failed due to error: {str(e)}")

        # Report failure to CodePipeline if applicable
        if report_to_codepipeline and job_id:
            codepipeline.put_job_failure_result(
                jobId=job_id,
                failureDetails={'type': 'JobFailed', 'message': str(e)}
            )

        # Error response with CORS headers
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(f'Lambda failed: {str(e)}')
        }