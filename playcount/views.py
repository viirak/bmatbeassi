from django.views import View
from django.http import JsonResponse
from django.http import HttpResponse
from django.conf import settings
from playcount.utils import save_uploaded_chunks, get_media_file
from playcount.services import BackgroundService, CSVService


class JobCountView(View):
    """
    Handle request to job count process
    """

    def post(self, request):
        """
        Handle POST request method.
        Request body as Multipart form which contain "file" field.
        Reponse the background job id
        """
        file = request.FILES.get('file')
        if not file:
            data = dict(jobId=None, message="file is required.")
            return JsonResponse(data, status=400)

        tmp_uploaded_path = save_uploaded_chunks(file)
        job_id = BackgroundService().create_new(
            CSVService().process, args=(tmp_uploaded_path,))

        data = dict(jobId=job_id, message="file is being proccessed...")
        return JsonResponse(data, status=200)


class JobResultView(View):
    """
    Handle request to job result.
    """

    def get(self, request, job_id):
        """
        Handle GET method.
        Response job result (File) or status
        """
        job = BackgroundService().get_job(job_id)
        job_finished = job and job.get_status() == 'finished'
        if job_finished:
            file = get_media_file(job.result)
            cd = "attachment; filename=%s" % job.result
            response = HttpResponse(file, content_type="text/csv")
            response['Content-Disposition'] = cd
            return response
        msg = f"Job: {job.get_status()}" if job else "Job not found."
        return HttpResponse(msg, content_type="text/plain")