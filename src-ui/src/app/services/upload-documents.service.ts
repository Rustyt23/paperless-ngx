import { HttpEventType } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { BehaviorSubject, Subscription, first } from 'rxjs'
import { SETTINGS_KEYS } from '../data/ui-settings'
import { ConfigService } from './config.service'
import { DocumentService } from './rest/document.service'
import {
  FileStatusPhase,
  WebsocketStatusService,
} from './websocket-status.service'
import { SettingsService } from './settings.service'
import { ToastService } from './toast.service'

@Injectable({
  providedIn: 'root',
})
export class UploadDocumentsService {
  private documentService = inject(DocumentService)
  private websocketStatusService = inject(WebsocketStatusService)
  private configService = inject(ConfigService)
  private settingsService = inject(SettingsService)
  private toastService = inject(ToastService)

  private uploadSubscriptions: Array<Subscription> = []
  private splitPdfOnUpload = false
  private splitPdfOnUploadSubject = new BehaviorSubject<boolean>(false)

  splitPdfOnUpload$ = this.splitPdfOnUploadSubject.asObservable()

  constructor() {
    const persistedPreference = this.settingsService.get(
      SETTINGS_KEYS.SPLIT_PDF_ENABLED
    )
    if (persistedPreference !== null && persistedPreference !== undefined) {
      this.setSplitPdfOnUploadInternal(persistedPreference, false)
    }

    this.configService.getConfig().subscribe((c) => {
      const storedPreference = this.settingsService.get(
        SETTINGS_KEYS.SPLIT_PDF_ENABLED
      )
      const effectivePreference =
        storedPreference !== null && storedPreference !== undefined
          ? storedPreference
          : !!c.split_pdf_on_upload
      this.setSplitPdfOnUploadInternal(effectivePreference, false)
    })
  }

  public setSplitPdfOnUpload(split: boolean, persist: boolean = true) {
    this.setSplitPdfOnUploadInternal(split, persist)
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

  private setSplitPdfOnUploadInternal(split: boolean, persist: boolean) {
    if (this.splitPdfOnUpload === split && !persist) {
      this.splitPdfOnUploadSubject.next(split)
      return
    }

    this.splitPdfOnUpload = split
    this.splitPdfOnUploadSubject.next(split)

    if (persist) {
      this.persistSplitPreference(split)
    }
  }

  private persistSplitPreference(split: boolean) {
    this.settingsService.set(SETTINGS_KEYS.SPLIT_PDF_ENABLED, split)
    this.settingsService
      .storeSettings()
      .pipe(first())
      .subscribe({
        error: (error) => {
          this.toastService.showError(
            $localize`An error occurred while saving your split PDF preference.`,
            error
          )
        },
      })
  }
}
