from drf_yasg.generators import OpenAPISchemaGenerator


class DrfYasgSchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=True):
        schema = super().get_schema(request, public)

        return schema
