from app import create_app, db
from app.models import Project
from app.yandex.webmaster import YandexWebmasterAPI
import requests

app = create_app()
with app.app_context():
    try:
        project = Project.query.get(2)
        if project:
            # Fix host format by removing https:// and keeping :443
            host_url = project.yandex_webmaster_host
            if host_url.startswith('https://'):
                host_url = host_url.replace('https://', 'https:')
            elif host_url.startswith('https:'):
                # Already in correct format
                pass
            else:
                host_url = 'https:' + host_url
            
            if not host_url.endswith(':443'):
                host_url += ':443'
                
            project.yandex_webmaster_host = host_url
            api = YandexWebmasterAPI(
                oauth_token=project.yandex_webmaster_token,
                user_id=project.yandex_webmaster_user_id
            )
            
            # Get user ID
            user_id = api.get_user_id()
            if not user_id:
                print("Could not get user ID")
            else:
                # Get list of hosts
                url = f'{api.base_url}/{user_id}/hosts'
                try:
                    response = requests.get(url, headers=api.headers)
                    response.raise_for_status()
                    data = response.json()
                    
                    print("\nAvailable hosts in Yandex.Webmaster:")
                    for host_data in data.get('hosts', []):
                        print(f"- {host_data.get('ascii_host_url')} (ID: {host_data.get('host_id')})")
                    print(f"\nLooking for host: {project.yandex_webmaster_host}")
                    
                    # Try to find the host
                    host_id = None
                    for host_data in data.get('hosts', []):
                        if host_data.get('host_id') == project.yandex_webmaster_host:
                            host_id = host_data.get('host_id')
                            break
                    
                    if host_id:
                        project.yandex_webmaster_host_id = host_id
                        db.session.commit()
                        print(f"Updated host_id to: {host_id}")
                    else:
                        print("Could not get host_id from API")
                except requests.exceptions.RequestException as e:
                    print(f"Error: {str(e)}")
    except Exception as e:
        print(f"Error: {str(e)}")
