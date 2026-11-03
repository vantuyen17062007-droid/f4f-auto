package com.f4f.autorunner.api

import com.google.gson.annotations.SerializedName

data class ApiResponse<T>(
    @SerializedName("status_code") val statusCode: Int,
    @SerializedName("message") val message: String?,
    @SerializedName("data") val data: T?
)

data class LoginData(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("user") val user: UserInfo
)

data class UserInfo(
    @SerializedName("id") val id: Long,
    @SerializedName("username") val username: String,
    @SerializedName("balance") val balance: Long,
    @SerializedName("balance_pending") val balancePending: Long?
)

data class AccountListData(
    @SerializedName("data") val list: List<SocialAccount>?
)

data class SocialAccount(
    @SerializedName("id") val id: Long,
    @SerializedName("name") val name: String?,
    @SerializedName("username") val username: String?,
    @SerializedName("status") val status: String?
)

data class JobListData(
    @SerializedName("jobs") val jobs: List<F4FJob>?
)

data class F4FJob(
    @SerializedName("id") val id: Long,
    @SerializedName("object_id") val objectId: String?,
    @SerializedName("link") val link: String?,
    @SerializedName("original_link") val originalLink: String?,
    @SerializedName("reward_amount") val rewardAmount: Int = 10,
    @SerializedName("remains") val remains: Any?,
    @SerializedName("type_job") var typeJob: String = "follow"
)

data class CompleteJobData(
    @SerializedName("coin_received") val coinReceived: Int?
)
