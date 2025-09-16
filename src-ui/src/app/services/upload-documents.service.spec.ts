import {
  HttpEventType,
  provideHttpClient,
  withInterceptorsFromDi,
} from '@angular/common/http'
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing'
import { TestBed } from '@angular/core/testing'
import { environment } from 'src/environments/environment'
import { UploadDocumentsService } from './upload-documents.service'
import {
  FileStatusPhase,
  WebsocketStatusService,
} from './websocket-status.service'
import { ConfigService } from './config.service'
import { of } from 'rxjs'

const STORAGE_KEY = 'paperless-ngx:upload:split-pdf-on-upload'

describe('UploadDocumentsService', () => {
  beforeEach(() => {
    localStorage.clear()

    TestBed.configureTestingModule({
      imports: [],
      providers: [
        UploadDocumentsService,
        WebsocketStatusService,
        {
          provide: ConfigService,
          useValue: { getConfig: () => of({ split_pdf_on_upload: false }) },
        },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })
  })

  afterEach(() => {
    TestBed.inject(HttpTestingController).verify()
  })

  it('calls post_document api endpoint on upload', () => {
    const uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    const httpTestingController = TestBed.inject(HttpTestingController)

    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    uploadDocumentsService.uploadFile(file)
    const req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )
    expect(req[0].request.method).toEqual('POST')
    expect(req[0].request.body.get('split_pdf')).toEqual('false')

    req[0].flush('123-456')
  })

  it('passes split preference', () => {
    const uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    const httpTestingController = TestBed.inject(HttpTestingController)

    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    uploadDocumentsService.setSplitPdfOnUpload(true)
    uploadDocumentsService.uploadFile(file)
    const req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )
    expect(req[0].request.body.get('split_pdf')).toEqual('true')
    req[0].flush('123-456')
  })

  it('updates progress during upload and failure', () => {
    const uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    const websocketStatusService = TestBed.inject(WebsocketStatusService)
    const httpTestingController = TestBed.inject(HttpTestingController)

    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    const file2 = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file2.pdf'
    )
    uploadDocumentsService.uploadFile(file)
    uploadDocumentsService.uploadFile(file2)

    expect(websocketStatusService.getConsumerStatusNotCompleted()).toHaveLength(
      2
    )
    expect(
      websocketStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
    ).toHaveLength(0)

    const req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    req[0].event({
      type: HttpEventType.UploadProgress,
      loaded: 100,
      total: 300,
    })

    expect(
      websocketStatusService.getConsumerStatus(FileStatusPhase.UPLOADING)
    ).toHaveLength(1)
  })

  it('updates progress on failure', () => {
    const uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    const websocketStatusService = TestBed.inject(WebsocketStatusService)
    const httpTestingController = TestBed.inject(HttpTestingController)

    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    uploadDocumentsService.uploadFile(file)

    let req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    expect(
      websocketStatusService.getConsumerStatus(FileStatusPhase.FAILED)
    ).toHaveLength(0)

    req[0].flush(
      {},
      {
        status: 400,
        statusText: 'failed',
      }
    )

    expect(
      websocketStatusService.getConsumerStatus(FileStatusPhase.FAILED)
    ).toHaveLength(1)

    uploadDocumentsService.uploadFile(file)

    req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    req[0].flush(
      {},
      {
        status: 500,
        statusText: 'failed',
      }
    )

    expect(
      websocketStatusService.getConsumerStatus(FileStatusPhase.FAILED)
    ).toHaveLength(2)
  })

  it('persists split preference changes', () => {
    const uploadDocumentsService = TestBed.inject(UploadDocumentsService)

    uploadDocumentsService.setSplitPdfOnUpload(true)
    expect(localStorage.getItem(STORAGE_KEY)).toEqual('true')

    uploadDocumentsService.setSplitPdfOnUpload(false)
    expect(localStorage.getItem(STORAGE_KEY)).toEqual('false')
  })

  it('restores persisted preference on initialization', () => {
    localStorage.setItem(STORAGE_KEY, 'true')

    const uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    const httpTestingController = TestBed.inject(HttpTestingController)

    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )

    uploadDocumentsService.uploadFile(file)

    const req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )

    expect(req[0].request.body.get('split_pdf')).toEqual('true')

    req[0].flush('123-456')
  })
})
