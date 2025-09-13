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
import { SettingsService } from './settings.service'
import { UploadDocumentsService } from './upload-documents.service'
import {
  FileStatusPhase,
  WebsocketStatusService,
} from './websocket-status.service'

describe('UploadDocumentsService', () => {
  let httpTestingController: HttpTestingController
  let uploadDocumentsService: UploadDocumentsService
  let websocketStatusService: WebsocketStatusService
  let settingsService: SettingsService

  beforeEach(() => {
    const settingsStub = {
      get: jest.fn().mockReturnValue(false),
    }

    TestBed.configureTestingModule({
      imports: [],
      providers: [
        UploadDocumentsService,
        WebsocketStatusService,
        { provide: SettingsService, useValue: settingsStub },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    })

    httpTestingController = TestBed.inject(HttpTestingController)
    uploadDocumentsService = TestBed.inject(UploadDocumentsService)
    websocketStatusService = TestBed.inject(WebsocketStatusService)
    settingsService = TestBed.inject(SettingsService)
  })

  afterEach(() => {
    httpTestingController.verify()
  })

  it('calls post_document api endpoint on upload', () => {
    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    uploadDocumentsService.uploadFile(file)
    const req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )
    expect(req[0].request.method).toEqual('POST')

    req[0].flush('123-456')
  })

  it('appends split flag when enabled', () => {
    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    ;(settingsService.get as jest.Mock).mockReturnValue(true)
    uploadDocumentsService.uploadFile(file)
    const req = httpTestingController.match(
      `${environment.apiBaseUrl}documents/post_document/`
    )
    expect(req[0].request.body.get('split')).toBe('true')

    req[0].flush('123-456')
  })

  it('updates progress during upload and failure', () => {
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
})
