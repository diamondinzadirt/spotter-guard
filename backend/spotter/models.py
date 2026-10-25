from django.db import models


class HereUsage(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    requests_used = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "HERE usage budget"
