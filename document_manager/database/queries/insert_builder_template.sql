INSERT INTO public.templates (code, name)
VALUES (%s, %s)
RETURNING template_id;
