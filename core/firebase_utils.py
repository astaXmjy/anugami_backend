# firebase_utils.py
import firebase_admin
from firebase_admin import credentials, firestore, auth, messaging
from django.conf import settings


class FirebaseService:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            # Initialize Firebase Admin SDK
            if not firebase_admin._apps:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(
                    cred
                )

            # Initialize Firestore client
            cls._firestore_client = firestore.client()
            cls._instance = super().__new__(cls)

        return cls._instance

    @property
    def firestore(self):
        return self._firestore_client

    def create_document(self, collection, data, document_id=None):
        """
        Create a document in a Firestore collection
        """
        if document_id:
            return self.firestore.collection(collection).document(document_id).set(data)
        else:
            return self.firestore.collection(collection).add(data)

    def get_document(self, collection, document_id):
        """
        Retrieve a document from a Firestore collection
        """
        return self.firestore.collection(collection).document(document_id).get()

    def update_document(self, collection, document_id, data):
        """
        Update a document in a Firestore collection
        """
        return self.firestore.collection(collection).document(document_id).update(data)

    def delete_document(self, collection, document_id):
        """
        Delete a document from a Firestore collection
        """
        return self.firestore.collection(collection).document(document_id).delete()

    def create_auth_user(self, email, password):
        """
        Create a new Firebase Authentication user
        """
        try:
            user = auth.create_user(email=email, password=password)
            return user
        except Exception as e:
            print(f"Firebase user creation error: {e}")
            return None

    def send_notification(self, token, title, body, data=None):
        """
        Send Firebase Cloud Messaging notification
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=token,
                data=data or {},
            )
            return messaging.send(message)
        except Exception as e:
            print(f"Notification send error: {e}")
            return None


# Instantiate the service
firebase_service = FirebaseService()
