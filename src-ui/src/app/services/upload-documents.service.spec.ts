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
import { Subject, of } from 'rxjs'

describe('UploadDocumentsService', () => {
  let configServiceMock: {
    getConfig: jest.Mock
    saveConfig: jest.Mock
  }

  beforeEach(() => {
    configServiceMock = {
      getConfig: jest
        .fn()
        .mockReturnValue(of({ id: 1, split_pdf_on_upload: false })),
      saveConfig: jest
        .fn()
        .mockImplementation(({ id, split_pdf_on_upload }) =>
          of({ id, split_pdf_on_upload })
        ),
    }

    TestBed.configureTestingModule({
      imports: [],
      providers: [
        UploadDocumentsService,
        WebsocketStatusService,
        { provide: ConfigService, useValue: configServiceMock },
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

    configServiceMock.saveConfig.mockReturnValue(
      of({ id: 1, split_pdf_on_upload: true })
    )

    const file = new File(
      [new Blob(['testing'], { type: 'application/pdf' })],
      'file.pdf'
    )
    uploadDocumentsService.setSplitPdfOnUpload(true)
    expect(configServiceMock.saveConfig).toHaveBeenCalledWith({
      id: 1,
      split_pdf_on_upload: true,
    })
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
    expect(configServiceMock.saveConfig).toHaveBeenCalledWith({
      id: 1,
      split_pdf_on_upload: true,
    })

    uploadDocumentsService.setSplitPdfOnUpload(false)
    expect(configServiceMock.saveConfig).toHaveBeenLastCalledWith({
      id: 1,
      split_pdf_on_upload: false,
    })
  })

  it('initializes split preference from config', () => {
    configServiceMock.getConfig.mockReturnValue(
      of({ id: 1, split_pdf_on_upload: true })
    )

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

  it('persists pending preference once config loads', () => {
    const configSubject = new Subject<{ id: number; split_pdf_on_upload: boolean }>()
    configServiceMock.getConfig.mockReturnValue(configSubject.asObservable())
    configServiceMock.saveConfig.mockReturnValue(
      of({ id: 2, split_pdf_on_upload: true })
    )

    const uploadDocumentsService = TestBed.inject(UploadDocumentsService)

    uploadDocumentsService.setSplitPdfOnUpload(true)
    expect(configServiceMock.saveConfig).not.toHaveBeenCalled()

    configSubject.next({ id: 2, split_pdf_on_upload: false })
    configSubject.complete()

    expect(configServiceMock.saveConfig).toHaveBeenCalledWith({
      id: 2,
      split_pdf_on_upload: true,
    })
  })
})
