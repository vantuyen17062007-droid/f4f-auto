package com.f4f.autorunner.api

import com.google.gson.annotations.SerializedName

fun parseAnyToLong(value: Any?, fallback: Long = 0L): Long {
    if (value == null) return fallback
    return when (value) {
        is Number -> value.toLong()
        is String -> {
            val trimmed = value.trim()
            trimmed.toLongOrNull()
                ?: trimmed.toDoubleOrNull()?.toLong()
                ?: trimmed.replace(",", "").toDoubleOrNull()?.toLong()
                ?: fallback
        }
        else -> fallback
    }
}

fun parseAnyToInt(value: Any?, fallback: Int = 0): Int {
    return parseAnyToLong(value, fallback.toLong()).toInt()
}

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
        if (balance == null) return "0 xu"
        if (balance is String && (balance.contains("coin") || balance.contains("xu"))) return balance
        val num = parseAnyToLong(balance, -1L)
        return if (num >= 0) "$num xu" else balance.toString()
    }

    fun getNumericBalance(): Int {
        return parseAnyToInt(balance, 0)
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
        return parseAnyToInt(rewardAmount, 10)
    }
}

data class CompleteJobData(
    @SerializedName("coin_received") val coinReceived: Any? = null
) {
    fun getCoinReceivedInt(fallback: Int): Int {
        return parseAnyToInt(coinReceived, fallback)
    }
}
