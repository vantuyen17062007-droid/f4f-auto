package com.f4f.autorunner.api

import com.google.gson.Gson
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

class F4FApiClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()
    private val secret = "follow4follow_key".toByteArray(Charsets.UTF_8)
    private val baseUrl = "https://api.follow4follow.net"

    var token: String? = null
    var user: UserInfo? = null

    private fun generateSign(ts: Long, method: String, path: String): String {
        val payload = "$ts:${method.uppercase()}:$path".toByteArray(Charsets.UTF_8)
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(secret, "HmacSHA256"))
        return mac.doFinal(payload).joinToString("") { "%02x".format(it) }
    }

    private suspend fun <T> request(
        method: String,
        path: String,
        clazz: Class<T>?,
        jsonBody: String? = null,
        queryParams: Map<String, String>? = null
    ): ApiResponse<T> = withContext(Dispatchers.IO) {
        val ts = System.currentTimeMillis() / 1000
        val sign = generateSign(ts, method, path)

        var url = baseUrl + path
        if (!queryParams.isNullOrEmpty()) {
            val queryString = queryParams.entries.joinToString("&") { "${it.key}=${it.value}" }
            url += "?$queryString"
        }

        val requestBuilder = Request.Builder()
            .url(url)
            .addHeader("accept", "application/json")
            .addHeader("x-ts", ts.toString())
            .addHeader("x-sign", sign)
            .addHeader("origin", "https://follow4follow.net")
            .addHeader("referer", "https://follow4follow.net/")
            .addHeader(
                "user-agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

        if (path != "/user/auth/login" && !token.isNullOrEmpty()) {
            requestBuilder.addHeader("authorization", "Bearer $token")
        }

        val body = jsonBody?.toRequestBody("application/json; charset=utf-8".toMediaType())
        when (method.uppercase()) {
            "GET" -> requestBuilder.get()
            "POST" -> requestBuilder.post(body ?: "".toRequestBody(null))
            else -> throw IllegalArgumentException("Unsupported HTTP method: $method")
        }

        val response = client.newCall(requestBuilder.build()).execute()
        val responseBody = response.body?.string().orEmpty()

        val jsonObject = try {
            gson.fromJson(responseBody, JsonObject::class.java)
        } catch (e: Exception) {
            throw RuntimeException("Phản hồi không phải JSON: $responseBody")
        }

        val statusCode = if (jsonObject.has("status_code") && !jsonObject.get("status_code").isJsonNull) {
            jsonObject.get("status_code").asInt
        } else {
            response.code
        }

        val message = if (jsonObject.has("message") && !jsonObject.get("message").isJsonNull) {
            jsonObject.get("message").asString
        } else {
            null
        }

        if (statusCode >= 400 || !response.isSuccessful) {
            throw RuntimeException(message ?: "Lỗi máy chủ ($statusCode)")
        }

        val dataElement = jsonObject.get("data")
        val parsedData: T? = if (dataElement != null && !dataElement.isJsonNull && clazz != null) {
            gson.fromJson(dataElement, clazz)
        } else {
            null
        }

        return@withContext ApiResponse(statusCode, message, parsedData)
    }

    suspend fun login(user: String, pass: String): LoginData {
        val payload = mapOf("username" to user, "password" to pass)
        val res = request("POST", "/user/auth/login", LoginData::class.java, jsonBody = gson.toJson(payload))
        val data = res.data ?: throw RuntimeException("Dữ liệu đăng nhập trống!")
        this.token = data.accessToken
        this.user = data.user
        return data
    }

    suspend fun getAccounts(platform: String): List<SocialAccount> {
        val res = request(
            "GET",
            "/user/account/list",
            JsonElement::class.java,
            queryParams = mapOf("type" to platform.lowercase(), "page" to "1")
        )
        val dataElement = res.data ?: return emptyList()

        return try {
            if (dataElement.isJsonObject) {
                val obj = dataElement.asJsonObject
                if (obj.has("data") && obj.get("data").isJsonArray) {
                    val listType = object : TypeToken<List<SocialAccount>>() {}.type
                    gson.fromJson(obj.get("data"), listType)
                } else {
                    val listType = object : TypeToken<AccountListData>() {}.type
                    val accData: AccountListData? = gson.fromJson(obj, listType)
                    accData?.list.orEmpty()
                }
            } else if (dataElement.isJsonArray) {
                val listType = object : TypeToken<List<SocialAccount>>() {}.type
                gson.fromJson(dataElement, listType)
            } else {
                emptyList()
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun getJobs(platform: String, uid: String, typeJob: String = "follow"): List<F4FJob> {
        val res = request(
            "GET",
            "/user/earn-coin",
            JobListData::class.java,
            queryParams = mapOf(
                "platform" to platform.lowercase(),
                "type" to typeJob,
                "refresh" to "1",
                "uid" to uid
            )
        )
        return res.data?.jobs.orEmpty()
    }

    suspend fun completeJob(
        platform: String,
        jobId: Long,
        accountId: Long,
        typeJob: String = "follow"
    ): CompleteJobData? {
        val payload = mapOf(
            "job_id" to jobId,
            "account_id" to accountId,
            "type" to platform.lowercase(),
            "type_job" to typeJob
        )
        val res = request(
            "POST",
            "/user/earn-coin/complete-job",
            CompleteJobData::class.java,
            jsonBody = gson.toJson(payload)
        )
        return res.data
    }

    suspend fun skipJob(
        platform: String,
        jobId: Long,
        accountId: Long,
        uid: String,
        objectId: String
    ): Boolean {
        return try {
            val payload = mapOf(
                "job_id" to jobId,
                "account_id" to accountId,
                "uid" to uid,
                "object_id" to objectId,
                "type" to platform.lowercase()
            )
            val res = request(
                "POST",
                "/user/earn-coin/skip-job",
                Any::class.java,
                jsonBody = gson.toJson(payload)
            )
            res.statusCode == 200
        } catch (_: Exception) {
            false
        }
    }
}
