from yapsy.IPlugin import IPlugin


class IRuntimeEnvironment(IPlugin):

    """
    Runtime Environment Plugin Interface

    Subclasses of this class can be used to specify environment specific
    parameters for the crawls. These include: how to name a container, how to
    link the container logs in the host (i.e. the --linkContainerLogs arg).
    """
    # TODO-ricarkol: only applies to containers at the moment.
    # TODO-ricarkol: options should define an actual explicit list of params.
    def get_environment_name(self):
        """Returns a unique string that identifies this environment
        """
        raise NotImplementedError()

    def get_container_namespace(self, long_id, options):
        """
	Specifies how to create the namespace of a container. This is a string
	that uniquely identifies a container instance. The default
	implementation, class CloudsightEnvironment, uses
	<HostIP>/<ContainerName>, but some organizations might prefer something
	else like: <DatacenterID>/<TenantID>/<AppContainerID>.  This is done by
	implementing the get_container_namespace() method.

        :param long_id: The container ID.
	:param options: Dictionary with "options". XXX-ricarkol should define
	                an actual explicit list of params.
        """
        raise NotImplementedError()

    def get_container_log_file_list(self, long_id, options):
        """
	Specifies what are the containers logs linked in the host (i.e. the
	--linkContainerLogs arg). The default implementation, class
	CloudsightEnvironment, uses the list in defaults.py:default_log_files.

        :param long_id: The container ID.
	:param options: Dictionary with "options".
        """
        raise NotImplementedError()

    def get_container_log_prefix(self, long_id, options):
        """
	Specifies where are the containers logs linked in the host (i.e. the
	--linkContainerLogs arg).  By default, a container log like /log/a.log
	is linked to <HostLogBaseDir>/<HostIP>/<ContainerName>/log/a.log, but
	it might be desirable to specify another way of constructing this path.
	This is done by implementing the get_container_log_prefix() function.

        :param long_id: The container ID.
	:param options: Dictionary with "options".
        """
        raise NotImplementedError()
