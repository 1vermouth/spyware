import os
from dropbox import DropboxOAuth2FlowNoRedirect
APP_KEY          = os.getenv("APP_KEY")
APP_SECRET       = os.getenv("APP_SECRET")

auth_flow = DropboxOAuth2FlowNoRedirect(
    APP_KEY,
    consumer_secret=APP_SECRET,
    token_access_type='offline'
 )
authorize_url = auth_flow.start()
print(authorize_url)
auth_code = input("Enter code:").strip()
oauth_result = auth_flow.finish(auth_code)
REFRESH_TOKEN = oauth_result.refresh_token
print("Refresh Token: ", REFRESH_TOKEN)