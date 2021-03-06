from mdb.models import *
from django.contrib import admin

class Ip6AddressInline(admin.TabularInline):
	model = Ip6Address
	extra = 0

class InterfaceInline(admin.TabularInline):
	inlines = [Ip6AddressInline]
	model = Interface
	extra = 0

class HostAdmin(admin.ModelAdmin):
	ordering = ('hostname',)
	inlines = [InterfaceInline]
	list_display = ['hostname', 'owner', 'host_type', 'location', 'mac_addresses', 'ip_addresses', 'in_domain', 'ipv6_enabled']
	readonly_fields = ['kerberos_principal_name', 'kerberos_principal_created_date',
			'kerberos_principal_created']
        search_fields = ['hostname', 'location', 'interface__macaddr','interface__ip4address__address']
	fieldsets = (
		('Owner Information', {
			'fields' : ( 'owner', 'location', 'description' )
		}),
		('Hardware and Software Information', {
			'fields' : ( ('brand', 'model'), 'serial_number', ('hostname', 'host_type' ),
				('operating_system', 'virtual' ) )
		}),
		('Domain and Kerberos Information', {
			'description' : 'If this host is a member of the LDAP domain, you need to tick the request kerberos principal checkbox. A principal will then be created for the host.',
			'classes' : [ 'collapse' ],
			'fields' : ( 'request_kerberos_principal', 'kerberos_principal_created',
				('kerberos_principal_name', 'kerberos_principal_created_date'))
		}),
	)

class Ip4AddressInline(admin.TabularInline):
	model = Ip4Address
	extra = 0
	readonly_fields = ['address']

class DhcpOptionInline(admin.TabularInline):
	model = DhcpOption
	extra = 0

class DhcpCustomFieldInline(admin.TabularInline):
	model = DhcpCustomField
	extra = 0

class SubnetAdmin(admin.ModelAdmin):
	list_display = ['name', 'network', 'netmask', 'num_addresses', 'broadcast_address', 'first_address', 'last_address']
	inlines = [DhcpOptionInline,DhcpCustomFieldInline,Ip4AddressInline]

class DomainSrvRecordInline(admin.TabularInline):
	model = DomainSrvRecord
	extra = 0

class DomainTxtRecordInline(admin.TabularInline):
	model = DomainTxtRecord
	extra = 0

class DomainCnameRecordInline(admin.TabularInline):
	model = DomainCnameRecord
	extra = 0

class DomainARecordInline(admin.TabularInline):
	model = DomainARecord
	extra = 0

class DomainAdmin(admin.ModelAdmin):
	inlines = [DomainSrvRecordInline, DomainTxtRecordInline, DomainARecordInline, DomainCnameRecordInline]
	list_display = ['domain_name', 'domain_soa', 'domain_admin', 'num_records', 'domain_ipaddr']
        search_fields = ['domain_name']

class HostTypeAdmin(admin.ModelAdmin):
	list_display = ['host_type', 'description', 'num_members']

class OperatingSystemAdmin(admin.ModelAdmin):
	list_display = ['name', 'version', 'architecture']

admin.site.register(Domain, DomainAdmin)
admin.site.register(Host, HostAdmin)
admin.site.register(Ip4Subnet, SubnetAdmin)
admin.site.register(Ip6Subnet)
admin.site.register(Ip6Address)
admin.site.register(Nameserver)
admin.site.register(MailExchange)
admin.site.register(OperatingSystem, OperatingSystemAdmin)
admin.site.register(OsArchitecture)
admin.site.register(HostType, HostTypeAdmin)
admin.site.register(DhcpConfig)
admin.site.register(DhcpOption)
