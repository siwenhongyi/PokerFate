local P = {
    curData = nil,
    iap_infos = nil,    -- 缓存的已经支付但还没上报的信息
    ios_skus = {},
}
PayHelper = P

-- 谷歌支付成功
function onGooglePayResult(info)
    print("onGooglePayResult ", info)
    local d = json.decode(info)
    if 0 == d.code then
        UiManager:showToast(_T("LAB_PURCHASE_SUC"))
        local sd = json.decode(string.urldecode(d.signtureData))

        _onPaySucces({
            token = d.token,
            signature = d.signture or "",
            signatureData = d.signtureData or "",
            pid = sd.productId,
        })

        CS.PayHelper.consumeProduct(d.token)
    else
        print("[PayHelper] pay fail!", d.code)
        -- UiManager:showToast(_T("LAB_PURCHASE_FAIL") .. d.code)
        -- if P.curData then
            ShopModel:doPayFail()
        -- end
    end
end

function onAppPaySuccess(info, transaction_id)
    print("onAppPaySuccess ", info, transaction_id)
    UiManager:showToast(_T("LAB_PURCHASE_SUC"))
    local infos, skuId, token, userId
    infos = string.split(info,"|", 1)
    skuId = infos[1];
    token = infos[2];

    if not P.order_id then
        P.order_id = LocalStore:getStringForKey("last_pay_order", "")
    end
    _onPaySucces({
        token = token,
        signature = "",
        signatureData = "",
        pid = skuId,
        order_id = P.order_id,
        transaction_id = transaction_id,
    })
    CS.PayHelper.consumeProduct(skuId)
end

function onAppPayFail(code)
    print("[PayHelper] app pay fail", code)
    if 1 == code then   -- SKErrorClientInvalid 无效请求
    elseif 2 == code then -- SKErrorPaymentCancelled 取消支付
    elseif 3 == code then -- SKErrorPaymentInvalid 无效支付
    elseif 4 == code then -- SKErrorPaymentNotAllowed 支付被拒绝
    elseif 5 == code then -- SKErrorStoreProductNotAvailable 商品不存在
    else    -- SKErrorUnknow 未知错误
    end
    ShopModel:doPayFail()
end

function onAppConsumeSuccess(id)
end

function onAppProductInfos(info)
    -- print("[PayHelper] onAppProductInfos", info)
    P.ios_skus = {}
    local infos = string.split(info, ":")
    for k, v in ipairs(infos) do
        local vals = string.split(v, "@")
        if #vals >= 3 then
            local productId, coin, pri = vals[1], vals[2], vals[3]
            -- if coin == "USD" then
            --     pri = "$"..pri
            -- else
                pri =  coin .. " " .. pri
            -- end
            P.ios_skus[productId] = {productId = productId, pri = pri, coin = coin}
        end
    end
end

function onPcPayResult(info)
    -- local d = json.decode(info)
    -- print("onPcPayResult ", info, d)
    -- if 0 == d.code then
    --     UiManager:showToast(_T("LAB_PURCHASE_SUC"))
    --     local tbr = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "N", "M", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
    --     local token = ""
    --     for i = 1, 32 do
    --         token = token .. tbr[math.random(#tbr)]
    --     end
    --     print("token ==", token)
        
    --     P.curData = nil
    --     -- local data = getShopCfgData(d.pid)
    --     -- _onPaySucces({
    --     --     token = token,
    --     --     shop_type = self.data.shop_type,
    --     --     id = data.id,
    --     --     pid = info.pid,
    --     --     pri = data.priInt,
    --     -- })
    -- else
    --     UiManager:showToast(_T("LAB_PURCHASE_FAIL") .. d.code)
    --     ShopModel:doPayFail()
    -- end
end

function _onPaySucces(info)
    ShopModel:doPaySuc(info)
    if P:addIapInfo(info) or true then
        doPaySucces(info, successCb)
    end
end

function doPaySucces(info, successCb)
    if not info.token or "" == info.token then
        P:removeIapInfo(info)
        return
    end
    if not PlayerModel or not PlayerModel:isLogin() then
        return
    end
    if bee.isAndroid then
        Net:post("shop/googlePay", {pid = info.pid, token = info.token}, function(data)
            print("shop/googlePay resp ==== ", json.encode(data))
            P:removeIapInfo(info)
            if data.code ~= 0 then
                return
            end
            ShopModel:onPaySucces(info, data)
        end)
    elseif bee.isIos then
        if info.transaction_id then
            Net:post("v2/shop/applePay", {transaction_id = info.transaction_id}, function(data)
                print("v2/shop/applePay resp ==== ", json.encode(data))
                P:removeIapInfo(info)
                if data.code ~= 0 then
                    return
                end
                ShopModel:onPaySucces(info, data)
            end)
        else
            Net:post("shop/applePay", {pid = info.pid, token = info.token, order_id = info.order_id}, function(data)
                print("shop/applePay resp ==== ", json.encode(data))
                P:removeIapInfo(info)
                if data.code ~= 0 then
                    return
                end
                ShopModel:onPaySucces(info, data)
            end)
        end
    end
end

function P:initSku()
    local sku = ""
    for k,v in pairs(tpl_shop_pid) do
        if v.avenue_id == G_CHNL_ID then
            if "" == sku then
                sku = v.pid
            else
                sku = sku .. "," .. v.pid
            end
        end
    end
    
    if "" ~= sku then
        CS.PayHelper.setSkuList(sku)
    end
end

function P:getIapInfo()
    if not self.iap_infos then
        self.iap_infos = LocalStore:getTableData("iap_infos") or {}
    end
    return self.iap_infos
end

function P:addIapInfo(info)
    local infos = self:getIapInfo()
    for _, v in pairs(infos) do
        if v.token == info.token then
            return false
        end
    end
    infos[#infos + 1] = info
    LocalStore:saveTableData("iap_infos", infos)
    return true
end

function P:removeIapInfo(info)
    local infos = self:getIapInfo()
    for k, v in pairs(infos) do
        if v.token == info.token then
            table.remove(infos, k)
            LocalStore:saveTableData("iap_infos", infos)
            return
        end
    end
end

function P:pay(data, cb)
    self.curData = data
    self.cb = cb
    self.order_id = data.profileId or ""
    LocalStore:setStringForKey("last_pay_order", self.order_id)
    if bee.isIos then
        CS.PayHelper.pay(data.pid, data.uuid or "", PlayerModel:getUid())
    else
        CS.PayHelper.pay(data.pid, data.profileId or "", PlayerModel:getUid())
    end
    ShopModel._payInfo = nil
end

-- 检查还已经支付但还未发货的信息
function P:checkPurchase()
    local infos = self:getIapInfo()
    for _, v in ipairs(infos) do
        doPaySucces(v)
        return
    end
    CS.PayHelper.checkPurchases()
    bee.emit("evt_check_purchase")
end

-- 获取商品价格本地化信息 productId: id, pri: priId, coin: coin
function P:getProductInfo(productId)
    if bee.isAndroid then
        local info = CS.PayHelper.getSkuDetail(productId)
        if "" ~= info then
            local d = json.decode(info)
            return d
        end
    elseif bee.isIos then
        return self.ios_skus[productId]
    end
	return nil
end

