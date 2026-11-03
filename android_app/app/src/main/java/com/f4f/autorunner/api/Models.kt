package com.f4f.autorunner.api

import com.google.gson.annotations.SerializedName

data class ApiResponse<T>(
    @SerializedName("status_code") val statusCode: Int = 200,
    @SerializedName("message") val message: String? = null,
    @SerializedName("data") val data: T? = null
)

data class LoginData(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("user") val user: UserInfo
)

data class UserInfo(
    @SerializedName("id") val id: Long? = null,
    @SerializedName("username") val username: String? = null,
    @SerializedName("balance") val balance: Any? = null,
    @SerializedName("balance_pending") val balancePending: Any? = null
) {
    fun getDisplayBalance(): String {
        val raw = balance?.toString() ?: "0"
        return if (raw.contains("coin") || raw.contains("xu")) raw else "$raw xu"
    }

    fun getNumericBalance(): Int {
        val digits = balance?.toString()?.filter { it.isDigit() }
        return digits?.toIntOrNull() ?: 0
    }
}

data class AccountListData(
    @SerializedName("data") val list: List<SocialAccount>? = null
)

data class SocialAccount(
    @SerializedName("id") val id: Long? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("username") val username: String? = null,
    @SerializedName("uid") val uid: String? = null,
    @SerializedName("status") val status: String? = null
) {
    fun getId(): Long = id ?: 0L
    fun getDisplayName(): String = username ?: name ?: uid ?: "Tài khoản #$id"
}

data class JobListData(
    @SerializedName("jobs") val jobs: List<F4FJob>? = null
)

data class F4FJob(
    @SerializedName("id") val id: Long,
    @SerializedName("object_id") val objectId: String? = null,
    @SerializedName("link") val link: String? = null,
    @SerializedName("original_link") val originalLink: String? = null,
    @SerializedName("reward_amount") val rewardAmount: Any? = null,
    @SerializedName("remains") val remains: Any? = null,
    @SerializedName("type_job") var typeJob: String = "follow"
) {
    fun getRewardInt(): Int {
        val digits = rewardAmount?.toString()?.filter { it.isDigit() }
        return digits?.toIntOrNull() ?: 10
    }
}

data class CompleteJobData(
    @SerializedName("coin_received") val coinReceived: Any? = null
) {
    fun getCoinReceivedInt(fallback: Int): Int {
        val digits = coinReceived?.toString()?.filter { it.isDigit() }
        return digits?.toIntOrNull() ?: fallback
    }
}
