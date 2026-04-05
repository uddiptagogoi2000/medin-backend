from clerk_backend_api import Clerk
import os
from dotenv import load_dotenv

load_dotenv()

clerk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))
