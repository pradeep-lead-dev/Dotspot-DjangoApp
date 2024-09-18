from django.db import models

class Records(models.Model):
    client_name = models.CharField(max_length=100)
    dynamic_data = models.JSONField(default=dict)  # Storing dynamic columns as a JSON object

    def __str__(self):
        return self.name
