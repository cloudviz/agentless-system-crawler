VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  # allow specification of base box
  VM_BOX=ENV["VM_BOX"] || "bento/ubuntu14.04"
  config.vm.box = VM_BOX

  # optionally turn off vbguest auto_update
  # use test to stop it throwing error if vbguest gem is not installed
  if ENV["VBGUEST_AUTO"] == 'false'
    config.vbguest.auto_update = false
  end

  config.vm.provision "common" , type: "shell" do |c|
    c.path = "./vagrant-provision.sh"
  end
end
