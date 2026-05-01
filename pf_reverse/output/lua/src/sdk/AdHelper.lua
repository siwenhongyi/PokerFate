local P = {}

AdHelper = P

local helper = CS.AdHelper


----------------------------Revenue
bee.on("evt_RewardedAdRevenuePaid", function(info)
    print("==== gggggggg evt_RewardedAdRevenuePaid", info)
    local d = AdHelper:parseAdInfo(info)
end)

bee.on("evt_InterstitialAdRevenuePaid", function(info)
    print("==== gggggggg evt_InterstitialAdRevenuePaid", info)
    local d = AdHelper:parseAdInfo(info)
end)

bee.on("evt_BannerAdRevenuePaid", function(info)
    print("==== gggggggg evt_BannerAdRevenuePaid", info)
    local d = AdHelper:parseAdInfo(info)
end)

function P:parseAdInfo(info)
    if not info then
        return
    end
    -- info = "[AdInfo adUnitIdentifier: 3a75ce53e0c44d5b, adFormat: BANNER, networkName: Google AdMob, networkPlacement: ca-app-pub-7427835379701214/9869208662, creativeIdentifier: k15JZ_qpDPnXvcAPkoCcsQQ, placement: , revenue: 8.1143E-05, revenuePrecision: exact, latency: 3178, dspName: ]"
    info = string.replace(info, "[AdInfo ")
    info = string.replace(info, "]")
    infos = string.split(info, ", ")
    local d = {}
    for _, v in ipairs(infos) do
        local vals = string.split(v, ": ")
        d[vals[1]] = vals[2]
    end
    return d
end

function P:initAd()
    helper.initAd()
end

function P:showDebugger()
    helper.showDebugger()
end

function P:loadInterstitial()
    helper.loadInterstitial()
end

function P:isInterstitialReady()
    return helper.isInterstitialReady()
end

function P:isRewardedVideoAvailable(name)
    if bee.isPc then
        return true
    end
    if not helper.isRewardedVideoAvailable() then
        return false
    end
    if helper.isRewardedVideoPlacementCapped(name) then
        return false
    end
    return true
end

function P:showRewardedVideo(name)
    helper.showRewardedVideo(name or "DefaultRewardedVideo")
end

function P:loadRewardedVideo()
    helper.loadRewardedVideo()
end

function P:isInterstitialAvailable(name)
    if bee.isPc then
        return false
    end
    return helper.isInterstitialReady() and not helper.isInterstitialPlacementCapped(name)
end

function P:showInterstitial(name)
    helper.showInterstitial(name or "DefaultInterstitial")
end

function P:loadInterstitial()
	helper.loadInterstitial()
end

function P:isBannerReady()
    return helper.isBannerReady()
end

function P:loadBanner(name, pos)
    helper.loadBanner(name or "DefaultRewardedVideo", pos or 2)
end

function P:showBanner()
    helper.showBanner()
end

function P:hideBanner()
    helper.hideBanner()
end

function P:destroyBanner()
	helper.destroyBanner()
end

return P