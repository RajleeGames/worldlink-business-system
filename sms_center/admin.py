from django.contrib import admin

from .models import (
    SmsCampaign,
    SmsContact,
    SmsImportBatch,
    SmsRecipient,
    SmsSenderProfile,
    SmsTemplate,
)

admin.site.register(SmsContact)
admin.site.register(SmsTemplate)
admin.site.register(SmsSenderProfile)
admin.site.register(SmsCampaign)
admin.site.register(SmsRecipient)
admin.site.register(SmsImportBatch)
