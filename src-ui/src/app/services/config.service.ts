import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Observable, first, map } from 'rxjs'
import { environment } from 'src/environments/environment'
import { PaperlessConfig } from '../data/paperless-config'
import { ObjectWithId } from '../data/object-with-id'

@Injectable({
  providedIn: 'root',
})
export class ConfigService {
  protected http = inject(HttpClient)

  protected baseUrl: string = environment.apiBaseUrl + 'config/'

  getConfig(): Observable<PaperlessConfig> {
    return this.http.get<[PaperlessConfig]>(this.baseUrl).pipe(
      first(),
      map((configs) => configs[0])
    )
  }

  saveConfig(
    config: Partial<PaperlessConfig> & ObjectWithId
  ): Observable<PaperlessConfig> {
    // dont pass string
    if (typeof config.app_logo === 'string') delete config.app_logo
    return this.http
      .patch<PaperlessConfig>(`${this.baseUrl}${config.id}/`, config)
      .pipe(first())
  }

  uploadFile(
    file: File,
    configID: number,
    configKey: string
  ): Observable<PaperlessConfig> {
    let formData = new FormData()
    formData.append(configKey, file, file.name)
    return this.http
      .patch<PaperlessConfig>(`${this.baseUrl}${configID}/`, formData)
      .pipe(first())
  }
}
