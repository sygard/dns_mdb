from django.db import models
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver

from validators import validate_hostname

import ipaddr
import datetime
import re

# Create your models here.

class Nameserver(models.Model):
	hostname = models.CharField(max_length=256)
	
	def __unicode__(self):
		return self.hostname

class MailExchange(models.Model):
	priority = models.IntegerField()
	hostname = models.CharField(max_length=256)

	def __unicode__(self):
		return "(" + str(self.priority) + ") " + self.hostname

class Domain(models.Model):
	domain_name = models.CharField(max_length=256)
	domain_soa = models.CharField(max_length=256)
	domain_ttl = models.IntegerField(default=60)
	domain_serial = models.IntegerField(default=1)
	domain_active_serial = models.IntegerField(default=0, editable=False)
	domain_refresh = models.IntegerField(default=28800)
	domain_retry = models.IntegerField(default=7200)
	domain_expire = models.IntegerField(default=604800)
	domain_minimum_ttl = models.IntegerField(default=86400)
	domain_admin = models.EmailField()
	domain_ipaddr = models.IPAddressField()
	domain_filename = models.CharField(max_length=256)
	created_date = models.DateTimeField(auto_now_add=True)

	domain_nameservers = models.ManyToManyField(Nameserver)
	domain_mailexchanges = models.ManyToManyField(MailExchange)

	def __unicode__(self):
		return self.domain_name

	def num_records(self):
		size = {}
		size["cname"] = self.domaincnamerecord_set.count()
		size["srv"] = self.domainsrvrecord_set.count()
		size["txt"] = self.domaintxtrecord_set.count()
		size["a"]   = self.host_set.count()
		return size

	num_records.short_description = "Num Records"

	def __eq__(self, other):
		if not other: return False
		return self.domain_name == other.domain_name

	def zone_file_contents(self):
		content =  "; serial:%d\n" % self.domain_serial
		content += "; zone file for %s\n" % self.domain_name
		content += "; %s\n" % datetime.datetime.now()
		content += "; filename: %s\n" % self.domain_filename
		content += "$TTL %s\n" % self.domain_ttl
		content += "@ IN SOA %s. %s. (\n" % (self.domain_soa, self.domain_admin.replace("@", "."))
		content += "\t%d\t; serial\n" % self.domain_serial
		content += "\t%d\t; refresh\n" % self.domain_refresh
		content += "\t%d\t; retry\n" % self.domain_retry
		content += "\t%d\t; expire\n" % self.domain_expire
		content += "\t%d )\t; minimum ttl\n" % self.domain_minimum_ttl
		content += ";\n"

		for nameserver in self.domain_nameservers.all():
			content += "@\tIN\tNS\t%s.\n" % nameserver.hostname

		for mx in self.domain_mailexchanges.all():
			content += "@\t\tMX\t%d %s.\n" % (mx.priority, mx.hostname)

		if self.domain_ipaddr is not None:
			content += "@\tIN\tA\t%s\n" % self.domain_ipaddr
		
		content += "; SRV records\n"

		for srv in self.domainsrvrecord_set.all():
			content += unicode(srv) + "\n"

		content += "; A records\n"
		
		for a in self.domainarecord_set.all():
			content += unicode(a) + "\n"

		content += "; CNAME records \n"
		
		for cname in self.domaincnamerecord_set.all():
			content += "%s\tIN\tCNAME\t%s\n" % (cname.name, cname.target)
		
		content += "; TXT records \n"

		for txt in self.domaintxtrecord_set.all():
			content += unicode(txt) + "\n"
	
		content += "; HOST records\n"

		for interface in self.interface_set.all():
			host = interface.host
			if interface.ip4address:
				content += "%-20s\tIN\tA\t%s\n" % (host.hostname, interface.ip4address.address)
			for ipv6addr in interface.ip6address_set.all():
				content += "%-20s\tIN\tAAAA\t%s\n" % (host.hostname, ipv6addr.full_address())
		
		return content	

class DomainSrvRecord(models.Model):
	srvce = models.CharField(max_length=64)
	prot = models.CharField(max_length=64)
	name = models.CharField(max_length=128)
	priority = models.IntegerField()
	weight = models.IntegerField()
	port = models.IntegerField()
	target = models.CharField(max_length=256)
	domain = models.ForeignKey(Domain)
	created_date = models.DateTimeField(auto_now_add=True)
	
	def __unicode__(self):
		return self.srvce + "." + self.prot + "." + self.name + ". IN SRV " \
			+ str(self.priority) + " " + str(self.weight) + " " + \
			str(self.port) + " " + self.target + "."

class DomainTxtRecord(models.Model):
	name = models.CharField(max_length=256)
	target = models.CharField(max_length=256)
	domain = models.ForeignKey(Domain)
	created_date = models.DateTimeField(auto_now_add=True)

	def __unicode__(self):
		return self.name + " TXT " + self.target

class DomainCnameRecord(models.Model):
	name = models.CharField(max_length=256)
	target = models.CharField(max_length=256)
	domain = models.ForeignKey(Domain)
	created_date = models.DateTimeField(auto_now_add=True)

	def __unicode__(self):
		return self.name + " IN CNAME " + self.target

class DomainARecord(models.Model):
	name = models.CharField(max_length=256)
	target = models.CharField(max_length=256)
	domain = models.ForeignKey(Domain)
	created_date = models.DateTimeField(auto_now_add=True)

	def __unicode__(self):
		return self.name + " IN A " + self.target
	

class DhcpConfig(models.Model):
	serial = models.IntegerField()
	active_serial = models.IntegerField()
	name = models.CharField(max_length=255)
	authoritative = models.BooleanField()
	ddns_update_style = models.CharField(max_length=63)
	default_lease_time = models.IntegerField(default=600)
	max_lease_time = models.IntegerField(default=7200)
	log_facility = models.CharField(max_length=255)

	def dhcpd_configuration(self):
		content = "# Autogenerated configuration %s\n" % datetime.datetime.now()
		if self.authoritative:
			content += "authoritative;\n"
		content += "default-lease-time %d;\n" % self.default_lease_time
		content += "max-lease-time %d;\n" % self.max_lease_time
		content += "log-facility %s;\n" % self.log_facility
		content += "ddns-update-style %s;\n" % self.ddns_update_style
		

		# time to write the subnet definitions
		for subnet in self.ip4subnet_set.all():
			content += "\n# %s\n" % subnet.name
			content += "subnet %s netmask %s {\n" % (subnet.network, subnet.netmask)
			
			for option in subnet.dhcpoption_set.all():
				content += "\toption %s %s;\n" % (option.key, option.value)

			for option in subnet.dhcpcustomfield_set.all():
				content += "\t%s;\n" % option.value

			if subnet.dhcp_dynamic:
				content += "\trange %s %s;\n" \
					% (subnet.dhcp_dynamic_start, subnet.dhcp_dynamic_end)

			content += "}\n"

		# time to write host definitions
		for subnet in self.ip4subnet_set.all():
			for ip4address in subnet.ip4address_set.all():
				if ip4address.interface_set.count() == 0:
					continue
				interface = ip4address.interface_set.get()
				if not interface.dhcp_client:
					continue
				content += "\nhost %s {\n" % interface.host.hostname
				content += "\thardware ethernet %s;\n" % interface.macaddr
				content += "\tfixed-address %s.%s;\n" % \
					(interface.host.hostname, interface.domain.domain_name)
				if len(interface.pxe_filename) > 0:
					content += "\tfilename \"%s\";\n" % interface.pxe_filename
				content += "}\n"

		return content

	def __unicode__(self):
		return self.name

class Ip6Subnet(models.Model):
	name = models.CharField(max_length=255)
	network = models.CharField(max_length=255)
	netmask = models.IntegerField(default=64)
	created_date = models.DateTimeField(auto_now_add=True)
	domain_name = models.CharField(max_length=255, editable=False)
	domain_nameservers = models.ManyToManyField(Nameserver)
	domain_soa = models.CharField(max_length=255)
	domain_ttl = models.IntegerField(default=60)
	domain_serial = models.IntegerField(default=1)
	domain_active_serial = models.IntegerField(default=0, editable=False)
	domain_refresh = models.IntegerField(default=28800)
	domain_retry = models.IntegerField(default=7200)
	domain_expire = models.IntegerField(default=604800)
	domain_minimum_ttl = models.IntegerField(default=86400)
	domain_admin = models.EmailField()
	domain_filename = models.CharField(max_length=256)

	def __unicode__(self):
		return self.network + " (" + self.name + ")"

	def zone_file_contents(self, generate_unassigned = False):
		content = ""
		content += "; zone file for %s\n" % self.domain_name
		content += "; %s\n" % datetime.datetime.now()
		content += "; filename: %s\n" % self.domain_filename
		content += "$TTL %s\n" % self.domain_ttl
		content += "@ IN SOA %s. %s. (\n" % (self.domain_soa, \
			self.domain_admin.replace("@", "."))
		content += "\t%d\t; serial\n" % self.domain_serial
		content += "\t%d\t; refresh\n" % self.domain_refresh
		content += "\t%d\t; retry\n" % self.domain_retry
		content += "\t%d\t; expire\n" % self.domain_expire
		content += "\t%d )\t; minimum ttl\n" % self.domain_minimum_ttl
		content += ";\n"
		content += ";\n"

		for nameserver in self.domain_nameservers.all():
			content += "@\tIN\tNS\t%s.\n" % nameserver.hostname
		
		content += ";\n"

		# find the network
#		network = ipaddr.IPv6Address("%s::" % self.network)
#		content += "$ORIGIN " + ".".join(network.exploded.replace(":","")[:16])[::-1] + ".ip6.arpa.\n"

		for addr in self.ip6address_set.all():
#			if addr.interface_set.count() == 0: continue

			if addr.interface.domain == None:
				continue
			hostname = "%s.%s" % (addr.interface.host.hostname, addr.interface.domain.domain_name)
			
			ip = ipaddr.IPv6Address(self.network + addr.address)
			ip = ".".join(ip.exploded.replace(":","")[16:])[::-1]
			content += "%s\tPTR\t%s.\n" % (ip, hostname)

#				addr = ipaddr.IPv6Address("%s%s" % (interface.

#				content += "%20s\tIN\tPTR\t%s.\n" % (addr.address.split(".")[3], hostname)

		return content

class Ip4Subnet(models.Model):

	name = models.CharField(max_length=256)
	netmask = models.IPAddressField()
	network = models.IPAddressField()
	created_date = models.DateTimeField(auto_now_add=True)
	domain_name = models.CharField(max_length=255, editable=False)
	domain_nameservers = models.ManyToManyField(Nameserver)
	domain_soa = models.CharField(max_length=256)
	domain_ttl = models.IntegerField(default=60)
	domain_serial = models.IntegerField(default=1)
	domain_active_serial = models.IntegerField(default=0, editable=False)
	domain_refresh = models.IntegerField(default=28800)
	domain_retry = models.IntegerField(default=7200)
	domain_expire = models.IntegerField(default=604800)
	domain_minimum_ttl = models.IntegerField(default=86400)
	domain_admin = models.EmailField()
	domain_filename = models.CharField(max_length=256)

	dhcp_dynamic = models.BooleanField(default=False)
	dhcp_dynamic_start = models.IPAddressField(null=True, blank=True)
	dhcp_dynamic_end = models.IPAddressField(null=True, blank=True)
	dhcp_config = models.ForeignKey(DhcpConfig)
	
	def __unicode__(self):
		return self.network + " (" + self.name + ")"

	def num_addresses(self):
		subnet = ipaddr.IPv4Network(self.network + "/" + self.netmask)
		return subnet.numhosts
	
	def broadcast_address(self):
		subnet = ipaddr.IPv4Network(self.network + "/" + self.netmask)
		return subnet.broadcast

	def first_address(self):
		subnet = ipaddr.IPv4Network(self.network + "/" + self.netmask)
		return subnet.iterhosts().next()

	def last_address(self):
		subnet = ipaddr.IPv4Network(self.network + "/" + self.netmask)
		for curr in subnet.iterhosts():
			pass # horribly ineficcient

		return curr

	broadcast_address.short_description = 'broadcast'
	num_addresses.short_description = '#addresses'
	first_address.short_description = 'first address'
	last_address.short_description = 'last address'

	def zone_file_contents(self, generate_unassigned = False):
		content = ""
		content += "; zone file for %s\n" % self.domain_name
		content += "; %s\n" % datetime.datetime.now()
		content += "; filename: %s\n" % self.domain_filename
		content += "$TTL %s\n" % self.domain_ttl
		content += "@ IN SOA %s. %s. (\n" % (self.domain_soa, \
			self.domain_admin.replace("@", "."))
		content += "\t%d\t; serial\n" % self.domain_serial
		content += "\t%d\t; refresh\n" % self.domain_refresh
		content += "\t%d\t; retry\n" % self.domain_retry
		content += "\t%d\t; expire\n" % self.domain_expire
		content += "\t%d )\t; minimum ttl\n" % self.domain_minimum_ttl
		content += ";\n"
		content += ";\n"

		for nameserver in self.domain_nameservers.all():
			content += "@\tIN\tNS\t%s.\n" % nameserver.hostname
		
		content += ";\n"

		for addr in self.ip4address_set.all():
			if addr.interface_set.count() == 0 and generate_unassigned:
				content += "%s\tIN\tPTR\t%s.%s\n" % \
					(addr.address, addr.address.split(".")[3], \
					"dhcp.neuf.no.")
				continue

			for interface in addr.interface_set.all():
				if interface.domain == None and generate_unassigned:
					content += "%s\tIN\tPTR\t%s.%s.\n" % \
						(addr.address, \
						addr.address.split(".")[3], \
						"dhcp.neuf.no")

				else:
					hostname = "%s.%s" % \
						(interface.host.hostname, \
						interface.domain.domain_name)
					content += "%-20s\tIN\tPTR\t%s.\n" % \
						(addr.address.split(".")[3], hostname)

		return content

class DhcpOption(models.Model):
	key = models.CharField(max_length=255)
	value = models.CharField(max_length=255)
	ip4subnet = models.ForeignKey(Ip4Subnet)

	def __unicode__(self):
		return self.key + " " + self.value

class DhcpCustomField(models.Model):
	value = models.CharField(max_length=255)
	ip4subnet = models.ForeignKey(Ip4Subnet)

class Ip4Address(models.Model):
	subnet = models.ForeignKey(Ip4Subnet)
	address = models.IPAddressField()
	last_contact = models.DateTimeField()
	ping_avg_rtt = models.FloatField()

	def __unicode__(self):
		if self.interface_set.count() == 0:
			return self.address
		else:
			return "%s (%s)" % (self.address, self.interface_set.get().host.hostname )

	def assigned_to_host(self):
		self.interface_set.get().host

	assigned_to_host.short_description = "Assigned to Host"


class HostType(models.Model):
	host_type = models.CharField(max_length=64)
	description = models.CharField(max_length=1024)

	def __unicode__(self):
		return self.host_type

	def num_members(self):
		return self.host_set.count()

	class Meta:
		ordering = ("host_type",)

class OsArchitecture(models.Model):
	architecture = models.CharField(max_length=64)

	def __unicode__(self):
		return self.architecture

class OperatingSystem(models.Model):
	name = models.CharField(max_length=256)
	version = models.CharField(max_length=64)
	architecture = models.ForeignKey(OsArchitecture)

	def __unicode__(self):
		return self.name + " " + self.version + " (" + unicode(self.architecture) + ")"

	class Meta:
		ordering = ("name","version")

class Host(models.Model):
	location = models.CharField(max_length=1024)
	brand = models.CharField(max_length=1024)
	model = models.CharField(max_length=1024)
	owner = models.CharField(max_length=1024)
	hostname = models.CharField(max_length=64, validators=[validate_hostname])
	serial_number = models.CharField(max_length=256)
	description = models.CharField(max_length=1024)
	created_date = models.DateTimeField(auto_now_add=True)
	host_type = models.ForeignKey(HostType)
	virtual = models.BooleanField()
	operating_system = models.ForeignKey(OperatingSystem)

	request_kerberos_principal = models.BooleanField()
	kerberos_principal_created = models.BooleanField(editable=False)
	kerberos_principal_name = models.CharField(max_length = 256, editable=False)
	kerberos_principal_created_date = models.DateTimeField(null=True, blank=True, editable=False)

	def __unicode__(self):
		return self.hostname

	def in_domain(self):
		domains = []
		for interface in self.interface_set.all():
			if interface.domain:
				domains.append(unicode(interface.domain))
		return ",".join(domains)

	in_domain.short_description = "in domains"
	
	def ipv6_enabled(self):
		for interface in self.interface_set.all():
			if interface.ipv6_enabled():
				return True
		return False

        ipv6_enabled.boolean = True

	def mac_addresses(self):
		addresses = []
		for interface in self.interface_set.all():
			if interface.macaddr == None: continue
			addresses.append( interface.macaddr)
		return ",".join(addresses)

	def ip_addresses(self):
		addresses = []
		for interface in self.interface_set.all():
			if interface.ip4address == None: continue
			addresses.append( interface.ip4address.address )
		return ",".join(addresses)

	def get_ip_addresses(self):
		addresses = []
		for interface in self.interface_set.all():
			if interface.ip4address == None: continue
			addresses.append( interface.ip4address.address )
		return addresses

	def get_ip_addresses_for_domain(self, domain):
		addresses = []
		for interface in self.interface_set.all():
			if interface.ip4address == None: continue
			addresses.append( interface.ip4address.address )
		return addresses

class Interface(models.Model):
	name = models.CharField(max_length=128)
	macaddr = models.CharField(max_length=17)
	pxe_filename = models.CharField(max_length=64, blank=True)
	dhcp_client = models.BooleanField()
	host = models.ForeignKey(Host)
	ip4address = models.ForeignKey(Ip4Address, blank=True, null=True, unique=True)
	created_date = models.DateTimeField(auto_now_add=True)
	domain = models.ForeignKey(Domain)
	
	def __unicode__(self):
		return "%s (%s on %s)" % (self.macaddr, self.name, self.host.hostname)

	def ipv6_enabled(self):
		return self.ip6address_set.count() > 0;

class Ip6Address(models.Model):
	subnet = models.ForeignKey(Ip6Subnet)
	address = models.CharField(max_length=64)
	interface = models.ForeignKey(Interface)
	
	def full_address(self):
		return self.subnet.network + self.address

	def __unicode__(self):
		return "%s (%s on %s)" % (self.full_address(), self.interface.name, self.interface.host.hostname)


def format_domain_serial_and_add_one(serial):
	today = datetime.datetime.now()
	res = re.findall("^%4d%02d%02d(\d\d)$" %
		(today.year, today.month, today.day), str(serial), re.DOTALL)

	if len(res) == 0:
		""" This probably means that the serial is malformed
		or the date is wrong. We assume that if the date is wrong,
		it is in the past. Just create a new serial starting from 1."""
		return "%4d%02d%02d%02d" % \
			(today.year, today.month, today.day, 1)
	elif len(res) == 1:
		""" The serial contains todays date, just update it. """
		try:
			number = int(res[0])
		except:
			number = 1
		if number >= 99:
			""" This is bad... Just keep the number on 99.
			We also send a mail to sysadmins telling them that
			something is wrong..."""
			
		else:
			number += 1
		return "%4d%02d%02d%02d" % \
			(today.year, today.month, today.day, number )
	else:
		""" Just return the first serial for today. """
		return "%4d%02d%02d%02d" % \
			(today.year, today.month, today.day, 1 )
	


@receiver(post_save, sender=Ip4Subnet)
def create_ips_for_subnet(sender, instance, created, **kwargs):
	if not created:
		return
	
	subnet = ipaddr.IPv4Network(instance.network + "/" + instance.netmask)

	for addr in subnet.iterhosts():
		address = Ip4Address(address = str(addr), subnet=instance)
		address.save()
	
@receiver(pre_delete, sender=Ip4Subnet)
def delete_ips_for_subnet(sender, instance, **kwargs):
	
	for addr in instance.ip4address_set.all():
		addr.delete()

@receiver(pre_save, sender=Ip4Subnet)
def set_domain_name_for_subnet(sender, instance, **kwargs):
	# we assume that the reverse domain_name does not change
	if len(instance.domain_name) == 0:
		ipspl = instance.network.split(".")
		rev = "%s.%s.%s" % (ipspl[2], ipspl[1], ipspl[0])
		instance.domain_name = "%s.in-addr.arpa" % rev

	# update it's own serial
	if instance.domain_serial != None:
		instance.domain_serial = format_domain_serial_and_add_one(instance.domain_serial)

	# lets update the serial of the dhcp config
	# when the subnet is changed
	if instance.dhcp_config:
#		instance.dhcp_config.serial = instance.dhcp_config.serial + 1
		instance.dhcp_config.serial = format_domain_serial_and_add_one(instance.dhcp_config.serial)
		instance.dhcp_config.save()

@receiver(pre_save, sender=Ip6Subnet)
def set_domain_name_for_ipv6_subnet(sender, instance, **kwargs):
	if len(instance.domain_name) > 0:
		return

	network = ipaddr.IPv6Address("%s::" % instance.network)
	instance.domain_name = ".".join(network.exploded.replace(":","")[:16])[::-1] + ".ip6.arpa"

@receiver(post_save, sender=Interface)
def update_domain_serial_when_change_to_interface(sender, instance, created, **kwargs):
	if instance.domain != None:
		domain = instance.domain
		domain.domain_serial = format_domain_serial_and_add_one(domain.domain_serial)
		domain.save()
	
	if instance.ip4address != None:
		subnet = instance.ip4address.subnet
		subnet.domain_serial = format_domain_serial_and_add_one(subnet.domain_serial)
		subnet.save()

@receiver(post_save, sender=Host)
def update_domain_serial_when_change_to_host(sender, instance, created, **kwargs):
	for interface in instance.interface_set.all():
		if interface.domain != None:
			domain = interface.domain
			domain.domain_serial = \
				format_domain_serial_and_add_one(domain.domain_serial)
			domain.save()
		if interface.ip4address != None:
			subnet = interface.ip4address.subnet
			subnet.domain_serial = \
				format_domain_serial_and_add_one(subnet.domain_serial)
			subnet.save()

@receiver(pre_delete, sender=Interface)
def update_domain_serial_when_interface_deleted(sender, instance, **kwargs):
	if instance.domain != None:
		domain = instance.domain
		domain.domain_serial = domain.domain_serial + 1
		domain.save()
	
	if instance.ip4address != None:
		subnet = instance.ip4address.subnet
		subnet.domain_serial = subnet.domain_serial + 1
		subnet.save()

#@receiver(pre_save, sender=Domain)
#def update_domain_serial_when_domain_is_saved(sender, instance, **kwargs):
#	instance.domain_serial = format_domain_serial_and_add_one(instance.domain_serial)
