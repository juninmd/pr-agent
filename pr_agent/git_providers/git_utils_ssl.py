import os
from pr_agent.log import get_logger

def get_git_ssl_env() -> dict[str, str]:
    """
    Get git SSL configuration arguments for per-command use.
    This fixes SSL certificate issues when cloning repos with self-signed certificates.
    Returns the current environment with the addition of SSL config changes if any such SSL certificates exist.
    """
    ssl_cert_file = os.environ.get('SSL_CERT_FILE')
    requests_ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE')
    git_ssl_ca_info = os.environ.get('GIT_SSL_CAINFO')

    chosen_cert_file = ""

    # Try SSL_CERT_FILE first
    if ssl_cert_file:
        if os.path.exists(ssl_cert_file):
            if ((requests_ca_bundle and requests_ca_bundle != ssl_cert_file)
                    or (git_ssl_ca_info and git_ssl_ca_info != ssl_cert_file)):
                get_logger().warning(f"Found mismatch among: SSL_CERT_FILE, REQUESTS_CA_BUNDLE, GIT_SSL_CAINFO. "
                                     f"Using the SSL_CERT_FILE to resolve ambiguity.",
                                  artifact={"ssl_cert_file": ssl_cert_file, "requests_ca_bundle": requests_ca_bundle,
                                            'git_ssl_ca_info': git_ssl_ca_info})
            else:
                get_logger().info(f"Using SSL certificate bundle for git operations", artifact={"ssl_cert_file": ssl_cert_file})
            chosen_cert_file = ssl_cert_file
        else:
            get_logger().warning("SSL certificate bundle not found for git operations", artifact={"ssl_cert_file": ssl_cert_file})

    # Fallback to REQUESTS_CA_BUNDLE
    elif requests_ca_bundle:
        if os.path.exists(requests_ca_bundle):
            if (git_ssl_ca_info and git_ssl_ca_info != requests_ca_bundle):
                get_logger().warning(f"Found mismatch between: REQUESTS_CA_BUNDLE, GIT_SSL_CAINFO. "
                                     f"Using the REQUESTS_CA_BUNDLE to resolve ambiguity.",
                artifact = {"requests_ca_bundle": requests_ca_bundle, 'git_ssl_ca_info': git_ssl_ca_info})
            else:
                get_logger().info("Using SSL certificate bundle from REQUESTS_CA_BUNDLE for git operations",
                                  artifact={"requests_ca_bundle": requests_ca_bundle})
            chosen_cert_file = requests_ca_bundle
        else:
            get_logger().warning("requests CA bundle not found for git operations", artifact={"requests_ca_bundle": requests_ca_bundle})

    #Fallback to GIT CA:
    elif git_ssl_ca_info:
        if os.path.exists(git_ssl_ca_info):
            get_logger().info("Using git SSL CA info from GIT_SSL_CAINFO for git operations",
                              artifact={"git_ssl_ca_info": git_ssl_ca_info})
            chosen_cert_file = git_ssl_ca_info
        else:
            get_logger().warning("git SSL CA info not found for git operations", artifact={"git_ssl_ca_info": git_ssl_ca_info})

    else:
        get_logger().warning("Neither SSL_CERT_FILE nor REQUESTS_CA_BUNDLE nor GIT_SSL_CAINFO are defined, or they are defined but not found. Returning environment without SSL configuration")

    returned_env = os.environ.copy()
    if chosen_cert_file:
        returned_env.update({"GIT_SSL_CAINFO": chosen_cert_file, "REQUESTS_CA_BUNDLE": chosen_cert_file})
    return returned_env
