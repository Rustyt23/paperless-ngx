import { HttpEventType } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { BehaviorSubject, Subscription } from 'rxjs'
import { PaperlessConfig } from '../data/paperless-config'
import { ConfigService } from './config.service'
import { DocumentService } from './rest/document.service'
import {
  FileStatusPhase,
  WebsocketStatusService,
} from './websocket-status.service'

@Injectable({
  providedIn: 'root',
})
export class UploadDocumentsService {
  private documentService = inject(DocumentService)
  private websocketStatusService = inject(WebsocketStatusService)
  private configService = inject(ConfigService)

  private uploadSubscriptions: Array<Subscription> = []
  private splitPdfOnUpload = false
  private splitPdfOnUploadSubject = new BehaviorSubject<boolean>(false)
  private configId: number | null = null
  private pendingSplitPreference: boolean | null = null

  splitPdfOnUpload$ = this.splitPdfOnUploadSubject.asObservable()

  constructor() {
    this.fetchSplitPreference()
  }

  public setSplitPdfOnUpload(split: boolean, persist: boolean = true) {
    if (!persist) {
      this.applySplitPreference(split)
      return
    }

    if (this.configId === null) {
      this.pendingSplitPreference = split
      this.applySplitPreference(split)
      return
    }

    if (this.splitPdfOnUpload === split) {
      this.splitPdfOnUploadSubject.next(split)
      return
    }

    this.applySplitPreference(split)
    this.persistSplitPreference(split)
  }

  public uploadFile(file: File, splitPdfOnUpload = this.splitPdfOnUpload) {
    let formData = new FormData()
    formData.append('document', file, file.name)
    formData.append('from_webui', 'true')
    formData.append('split_pdf', splitPdfOnUpload ? 'true' : 'false')
    let status = this.websocketStatusService.newFileUpload(file.name)

    status.message = $localize`Connecting...`

    this.uploadSubscriptions[file.name] = this.documentService
      .uploadDocument(formData)
      .subscribe({
        next: (event) => {
          if (event.type == HttpEventType.UploadProgress) {
            status.updateProgress(
              FileStatusPhase.UPLOADING,
              event.loaded,
              event.total
            )
            status.message = $localize`Uploading...`
          } else if (event.type == HttpEventType.Response) {
            status.taskId = event.body['task_id'] ?? event.body.toString()
            status.message = $localize`Upload complete, waiting...`
            this.uploadSubscriptions[file.name]?.complete()
          }
        },
        error: (error) => {
          switch (error.status) {
            case 400: {
              this.websocketStatusService.fail(status, error.error.document)
              break
            }
            default: {
              this.websocketStatusService.fail(
                status,
                $localize`HTTP error: ${error.status} ${error.statusText}`
              )
              break
            }
          }
          this.uploadSubscriptions[file.name]?.complete()
        },
      })
  }

  private applySplitPreference(split: boolean) {
    this.splitPdfOnUpload = split
    this.splitPdfOnUploadSubject.next(split)
  }

  private fetchSplitPreference() {
    this.configService.getConfig().subscribe({
      next: (config) => {
        this.configId = config?.id ?? null

        if (this.pendingSplitPreference !== null) {
          const pending = this.pendingSplitPreference
          this.pendingSplitPreference = null

          if (config?.split_pdf_on_upload === pending) {
            this.applySplitPreference(!!config.split_pdf_on_upload)
          } else {
            this.persistSplitPreference(pending)
          }
          return
        }

        this.applySplitPreference(!!config?.split_pdf_on_upload)
      },
    })
  }

  private persistSplitPreference(split: boolean) {
    if (this.configId === null) {
      this.pendingSplitPreference = split
      return
    }

    const payload: Partial<PaperlessConfig> & { id: number } = {
      id: this.configId,
      split_pdf_on_upload: split,
    }

    this.configService.saveConfig(payload).subscribe({
      next: (config) => {
        this.configId = config?.id ?? this.configId
        this.applySplitPreference(!!config.split_pdf_on_upload)
      },
      error: () => {
        this.fetchSplitPreference()
      },
    })
  }
}
