import json
import boto3
import logging
import os
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_obj = boto3.client('s3')
codecommit = boto3.client('codecommit')
sns_send = boto3.client('sns')
codebuild = boto3.client('codebuild')

def get_or_create_sns_topic(topic_name):
    try:
        # List all topics
        response = sns_send.list_topics()
        for topic in response['Topics']:
            if topic_name in topic['TopicArn']:
                return topic['TopicArn']
        
        # If topic does not exist, create it
        response = sns_send.create_topic(Name=topic_name)
        return response['TopicArn']
    except ClientError as e:
        logger.error(f"Failed to create or get SNS topic {topic_name}: {e}")
        raise e

def subscribe_email_to_topic(topic_arn, email):
    try:
        sns_send.subscribe(
            TopicArn=topic_arn,
            Protocol='email',
            Endpoint=email,
            ReturnSubscriptionArn=True
        )
        logger.info(f"Subscription request sent for {email} to topic {topic_arn}")
    except ClientError as e:
        logger.error(f"Failed to subscribe {email} to topic {topic_arn}: {e}")

def unsubscribe_email_from_topic(subscription_arn):
    try:
        sns_send.unsubscribe(
            SubscriptionArn=subscription_arn
        )
        logger.info(f"Unsubscribed {subscription_arn}")
    except ClientError as e:
        logger.error(f"Failed to unsubscribe {subscription_arn}: {e}")

def process_sonarqube_result(event):
    try:
        body = json.loads(event['body'])
        sonar_status = body.get('qualityGate', {}).get('status', 'UNKNOWN')
        repo_name = body.get('project', {}).get('name', 'UNKNOWN')
        project_key = body.get('project', {}).get('key', 'UNKNOWN')
        branch_name = body.get('branch', {}).get('name', 'UNKNOWN')
        pr_triggered = body.get('properties', {}).get('sonar.analysis.pr_triggered', 'false').lower()
        pull_request_id = body.get('properties', {}).get('sonar.analysis.pull_request_id', '')
        revision_id = body.get('properties', {}).get('sonar.analysis.revision_id', '')
        source_commit = body.get('properties', {}).get('sonar.analysis.source_commit', '')
        destination_commit = body.get('properties', {}).get('sonar.analysis.destination_commit', '')
        pr_branch = body.get('properties', {}).get('sonar.analysis.pr_branch', '')
        pr_base = body.get('properties', {}).get('sonar.analysis.pr_base', '')
        jar_file_url = body.get('properties', {}).get('sonar.analysis.jar_file_url', '')

        logger.info("Parsed body: " + json.dumps(body))
        logger.info(f"SonarQube quality gate status: {sonar_status}")
        logger.info(f"PR triggered: {pr_triggered}")
        logger.info(f"JAR File URL: {jar_file_url}")

        return {
            'sonar_status': sonar_status,
            'repo_name': repo_name,
            'project_key': project_key,
            'branch_name': branch_name,
            'pr_triggered': pr_triggered,
            'pull_request_id': pull_request_id,
            'revision_id': revision_id,
            'source_commit': source_commit,
            'destination_commit': destination_commit,
            'pr_branch': pr_branch,
            'pr_base': pr_base,
            'jar_file_url': jar_file_url
        }
    except KeyError as e:
        logger.error(f"KeyError: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps(f'Missing key in payload: {e}')
        }
    except json.JSONDecodeError as e:
        logger.error(f"JSONDecodeError: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps(f'Error decoding JSON: {e}')
        }

def manage_sns_notifications(repo_name, project_key, branch_name, sonar_status, sonarqube_host, pr_triggered, pr_branch, pr_base, pull_request_id, jar_url):
    bucket_name = os.getenv('S3_BUCKET', 'cdk-data-pipeline-center-test')
    region = os.getenv('AWS_REGION', 'ap-southeast-1')

    mailing_list_key = "config/mailing_list.json"

    mail_list_raw_json = s3_obj.get_object(Bucket=bucket_name, Key=mailing_list_key)
    mail_list_json = mail_list_raw_json['Body'].read().decode('utf-8')
    MAIL_LIST = json.loads(mail_list_json)

    get_cc_repo_tag = codecommit.list_tags_for_resource(
        resourceArn=f'arn:aws:codecommit:{region}:482680362026:{repo_name}'
    )
    repo_tags = get_cc_repo_tag['tags']
    logger.info(f"The repo tags are {repo_tags}")

    relevant_emails = set()
    topic_arn = None

    for repo_tag_key, repo_tag_value in repo_tags.items():
        for mail_list_tag in MAIL_LIST['tags']:
            if repo_tag_key == mail_list_tag['key'] and repo_tag_value == mail_list_tag['value']:
                current_topic_name = f"cdx-sonarqube-notification-{repo_tag_value}"
                topic_arn = get_or_create_sns_topic(current_topic_name)
                
                for email in mail_list_tag['emails']:
                    relevant_emails.add(email)
                    logger.info(f"{email} is relevant for tag {repo_tag_key}:{repo_tag_value}")

    if not topic_arn:
        default_topic_name = "cdx-sonarqube-notification-default"
        topic_arn = get_or_create_sns_topic(default_topic_name)
        logger.info(f"Using default SNS topic: {default_topic_name}")

    next_token = None
    subscriptions = []
    while True:
        if next_token:
            response = sns_send.list_subscriptions_by_topic(TopicArn=topic_arn, NextToken=next_token)
        else:
            response = sns_send.list_subscriptions_by_topic(TopicArn=topic_arn)

        subscriptions.extend(response['Subscriptions'])
        next_token = response.get('NextToken')
        if not next_token:
            break

    subscribed_emails_set = {sub['Endpoint'] for sub in subscriptions if sub['Protocol'] == 'email'}
    subscribed_arns = {sub['SubscriptionArn']: sub['Endpoint'] for sub in subscriptions if sub['Protocol'] == 'email'}

    for email in relevant_emails:
        if email not in subscribed_emails_set:
            subscribe_email_to_topic(topic_arn, email)
        else:
            logger.info(f"{email} is already subscribed to {topic_arn}")

    for sub_arn, email in subscribed_arns.items():
        if email not in relevant_emails:
            unsubscribe_email_from_topic(sub_arn)

    if pr_triggered == 'true':
        sonarqube_link = f"{sonarqube_host}/dashboard?id={project_key}&pullRequest={pull_request_id}"
        pull_request_url = f"https://{region}.console.aws.amazon.com/codesuite/codecommit/repositories/{repo_name}/pull-requests/{pull_request_id}/details?region={region}"
        additional_info = (f"\nThis SonarQube Scan was triggered by Pull Request"
                           f"\nPR Branch: {pr_branch}\nPR Base: {pr_base}\nPull Request URL: {pull_request_url}")
        body = (f"SonarQube Quality Gate Status: {sonar_status}\n"
                f"Repository Name: {repo_name}\n"
                f"SonarQube Link: {sonarqube_link}\n")
        if jar_url:
            body += f"JAR File URL (Expired in 1 hour): {jar_url}\n"
        body += additional_info
    else:
        sonarqube_link = f"{sonarqube_host}/dashboard?id={project_key}&branch={branch_name}"
        body = (f"SonarQube Quality Gate Status: {sonar_status}\n"
                f"Repository Name: {repo_name}\n"
                f"Branch Name: {branch_name}\n"
                f"SonarQube Link: {sonarqube_link}\n")
        if jar_url:
            body += f"JAR File URL (Expired in 1 hour): {jar_url}"

    subject = f"SonarQube Scan Result for {repo_name}"
    try:
        sns_send.publish(
            TopicArn=topic_arn,
            Message=body,
            Subject=subject
        )
        logger.info(f"Notification sent to topic {topic_arn}")
    except ClientError as e:
        logger.error(f"Failed to send notification to topic {topic_arn}: {e}")

def lambda_handler(event, context):
    logger.info("Received event: " + json.dumps(event))
    sonarqube_host = os.getenv('SONARQUBE_HOST', 'http://localhost:9000')

    result = process_sonarqube_result(event)
    if 'statusCode' in result:
        return result

    jar_url = result.get('jar_file_url', '')

    if result['pr_triggered'] == 'true':
        try:
            sonarqube_link = f"{sonarqube_host}/dashboard?id={result['project_key']}&pullRequest={result['pull_request_id']}"
            comment_content = (
                f"SonarQube Result: {result['sonar_status']}.\n"
                f"SonarQube Dashboard: {sonarqube_link}"
            )
            codecommit.post_comment_for_pull_request(
                pullRequestId=result['pull_request_id'],
                repositoryName=result['repo_name'],
                beforeCommitId=result['destination_commit'],
                afterCommitId=result['source_commit'],
                content=comment_content
            )
            logger.info(f"Comment posted to pull request {result['pull_request_id']} successfully.")
        except ClientError as e:
            logger.error(f"Error posting comment for pull request: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps(f"Error posting comment for pull request: {e}")
            }

    manage_sns_notifications(
        result['repo_name'],
        result['project_key'],
        result['branch_name'],
        result['sonar_status'],
        sonarqube_host,
        result['pr_triggered'],
        result['pr_branch'],
        result['pr_base'],
        result['pull_request_id'],
        jar_url if jar_url else None
    )

    return {
        'statusCode': 200,
        'body': json.dumps('Process completed')
    }