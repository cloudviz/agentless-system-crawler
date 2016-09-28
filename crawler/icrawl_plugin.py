from yapsy.IPlugin import IPlugin


class IContainerCrawler(IPlugin):

    """
    Crawler plugin interface

    Subclasses of this class can be used to implement crawling functions
    for different systems.
    """

    def crawl(self, container_id):
        """
        Crawling function that should return a list of features for
        `container_id`. This function is called once for every container
        at every crawling interval.
        """
        raise NotImplementedError()

    def get_feature(self):
        """
        Returns the feature type as a string.
        """
        raise NotImplementedError()


class IVMCrawler(IPlugin):

    """
    Crawler plugin interface

    Subclasses of this class can be used to implement crawling functions
    for different systems.
    """

    def crawl(self, vm_desc):
        """
        Crawling function that should return a list of features for
        `vm_desc`. This should change to 'vm_name' after auto kernel version
        detection. This function is called once for every VM
        at every crawling interval.
        """
        raise NotImplementedError()

    def get_feature(self):
        """
        Returns the feature type as a string.
        """
        raise NotImplementedError()


class IHostCrawler(IPlugin):

    """
    Crawler plugin interface

    Subclasses of this class can be used to implement crawling functions
    for different host features (e.g. processes running in the host).
    """

    def crawl(self):
        """
        Crawling function that should return a list of features for the host.
        This function is called once at every crawling interval.
        """
        raise NotImplementedError()

    def get_feature(self):
        """
        Returns the feature type as a string.
        """
        raise NotImplementedError()
