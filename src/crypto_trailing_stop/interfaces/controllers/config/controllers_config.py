from authlib.integrations.starlette_client import OAuth
from dependency_injector import containers, providers

from crypto_trailing_stop.config.configuration_properties import ConfigurationProperties


class ControllersContainer(containers.DeclarativeContainer):
    configuration_properties = providers.Dependency()

    @staticmethod
    def _oauth_context(configuration_properties: ConfigurationProperties) -> OAuth:  # pragma: no cover
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=configuration_properties.google_oauth_client_id,
            client_secret=configuration_properties.google_oauth_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
        return oauth

    oauth_context: OAuth = providers.Singleton(_oauth_context, configuration_properties=configuration_properties)
