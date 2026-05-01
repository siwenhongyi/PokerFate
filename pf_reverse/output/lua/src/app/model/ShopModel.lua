---@class ShopModel
local P = class("ShopModel", BaseModel)

local SHOP_TYPE_CFG = {
    [1] = tpl_first_recharge,
    [2] = tpl_monthly_card,
    [3] = tpl_shop_role_skin,
    [4] = tpl_shop_gifts,
    [5] = tpl_shop_gifts,
    [6] = tpl_shop_exchange,
    [7] = tpl_shop_recharge,
    [8] = tpl_shop_recharge,
    [9] = tpl_shop_recharge,
    [10] = tpl_quick_purchase,
    [11] = tpl_shop_theme,
    [12] = tpl_shop_decoration,
    [13] = tpl_shop_decoration,
    [14] = tpl_shop_decoration,
    [15] = tpl_icebreaker_pack,
    [16] = tpl_shop_exchange,
    [17] = tpl_shop_exchange,
    [18] = tpl_shop_decoration,
    [19] = tpl_shop_activity_gifts,
    [10001] = tpl_shop_exchange,
    [10002] = tpl_shop_activity,
    [10003] = tpl_shop_activity,
    [20001] = tpl_shop_activity,
}
P.SHOP_TYPE_CFG = SHOP_TYPE_CFG

function P:ctor()
    self.saveData = {
        cloud = {
            pays = nil,     -- 支付成功历史信息 {{pid, price, dt}}
        }
    }

    self._shopLimitList = {}
    self._newitems = {}
    self._timeLimitItems = {}

    P.super.ctor(self)
end

function P:afterLogin()
    self._isShowShopPush = false
	self._monthly_card_exp = nil
    self._shopLimitList = {}
    self._initShopLimitList = nil

    self._newitems = {}
    if not self.cloud["newitems" .. PlayerModel:getUid()] then
        self.cloud["newitems" .. PlayerModel:getUid()] = {}
    end
    for k,v in pairs(self.cloud["newitems" .. PlayerModel:getUid()]) do
        if not self._newitems[v[1]] then
            self._newitems[v[1]] = {}
        end
        table.insert(self._newitems[v[1]], v[2])
    end

    self._timeLimitItems = {}
    if not self.cloud["timeLimitItems" .. PlayerModel:getUid()] then
        self.cloud["timeLimitItems" .. PlayerModel:getUid()] = {}
    end
    for k, v in pairs(self.cloud["timeLimitItems" .. PlayerModel:getUid()]) do
        if not self._timeLimitItems[v[1]] then
            self._timeLimitItems[v[1]] = {}
        end
        self._timeLimitItems[v[1]][v[2]] = 1
    end

    self:refreshShopNewTag()
end

function P:initInfo()
    -- if not self._monthly_card_exp then
    --     self:requestPayInfo()
    -- end
    if not self._initShopLimitList then
        self:requestShopLimitList()
    end
    if not self._initShopPid then
        self:requestShopPid()
    end
    self:refreshShopNewTag()
end

-- 获取最近 day 天的付费金额
function P:getPayAmount(day)
    if not self.cloud.pays then
        return 0
    end
    local amount = 0
    local dt = day and bee.getServerTime() - day * 86400 or 0
    for i = #self.cloud.pays, 1, -1 do
        if self.cloud.pays[i][3] < dt then
            break
        end
        amount = amount + self.cloud.pays[i][2]
    end
    return amount
end

-- 获取总充值金额
function P:getTotalPayAmount()
    if not self.cloud.pays then
        return 0
    end

    local amount = 0
    for k,v in pairs(self.cloud.pays) do
        amount = amount + v[2]
    end

    return amount
end

function P:getPidData(buy_id, avenue)
    if not avenue then
        avenue = G_CHNL_ID
    end
    local datas = get_tpl_subKey(tpl_shop_pid_list, "buy_id", buy_id)
    for _, v in ipairs(datas) do
        if v.avenue_id == avenue then
            return v
        end
    end
    return nil
end

function P:getPidDataByPid(pid, avenue)
    if not avenue then
        avenue = G_CHNL_ID
    end
    local datas = get_tpl_subKey(tpl_shop_pid_list, "pid", pid)
    if not datas then
        return
    end
    for _, v in ipairs(datas) do
        if v.avenue_id == avenue and v.pid == pid then
            return v
        end
    end
end

function P:getShopCfg(shop_type, buy_id)
    local shopCfg = SHOP_TYPE_CFG[shop_type]
    for k,v in pairs(shopCfg) do
        if v.buy_id == buy_id then
            return v
        end
    end
end

function P:setTextPrice(text, buy_id)
    local data = self:getPidData(buy_id)
    if data then
        bee.setText(text, self:getPriText(data))
    end
end

function P:pay(data, cb, tag, parentTag)
    if self._payLimitCd then
        if os.time() - self._payLimitCd <= 5 then
            UiManager:showToast(_T("ERR_SERVER_BUSY"))
            return
        end
        self._payLimitCd = nil
    end
    if not bee.checkCd("shop_purchase", 1) then
        return
    end

    if not PlayerModel:isCanPay() then
        UiManager:showToast(_T("LAB_SHOP_COMMON_35"))
        return
    end
    UiManager:showLoadingMask("PayMask")

    self.payData = data
    self.payTag = tag or 1
    self.parentTag = parentTag

    local pidCfg = self:getPidData(data.buy_id)

    local args = {}
    args.shop_type = data.shop_type
    args.id = data.id
    args.avenue_id = pidCfg.avenue_id
    args.pid = pidCfg.pid
    args.cur_id = PlayerModel:getCurId()
    args.currency = tpl_shop_cur_type[args.cur_id].code
    Net:post("shop/createOrder", args, function(info)
        if info.code ~= 0 then
            self:doPayFail(true)
            if info.code == tpl_HttpCode.HTTP_STEAM_IP_LIMIT_ERR.code then
                self._payLimitCd = os.time()
            end
            return
        end

        local params = {}
        for k,v in pairs(data) do
            params[k] = v
        end
        for k,v in pairs(pidCfg) do
            params[k] = v
        end
        params.profileId = info.order_id
        params.uuid = info.uuid
        PayHelper:pay(params, cb)

        self._orderData = args
        self._orderData.order_id = info.order_id
    end, function()
        self:doPayFail(true)
    end)
end

function P:PayTest(data)
    if bee.isRelease then
        return
    end
    
    local pidCfg = self:getPidData(data.buy_id, 5)
    local args = {}
    args.pid = pidCfg.pid
    args.token = "test"
    args.test = true
    args.shop_type = data.shop_type
    args.shop_id = data.id
    args.avenue_id = pidCfg.avenue_id
    
    Net:post("shop/googlePay", args, function(data)
        print("shop/googlePay PayTest resp ==== ", json.encode(data))
        if data.code ~= 0 then
            self:doPayFail(true)
            return
        end
        ShopModel:onPaySucces(args, data, 5)
        self:doPaySuc()
    end)
end

function P:doPayFail(noTip)
    if self.payData then
        self.payData = nil
    end

    -- if self._orderData then
    --     -- 取消服务器订单
    --     Net:post("shop/cancelOrder", self._orderData, function()
    --     end)
    --     self._orderData = nil
    -- end

    UiManager:hideLoadingMask("PayMask")
    if not noTip then
        UiManager:showToast(_T("LAB_SHOP_COMMON_17"))
    end

    self:setShopPledgeGiftRole()
end

function P:doPaySuc(info)
    UiManager:hideLoadingMask("PayMask")

    if self.payData then
        self.payData = nil
    end
    
    -- self:onSave()
end

function P:onPaySucces(info, data, testId)
    local pidData = self:getPidDataByPid(info.pid, testId)
    if pidData and data.item_list then
        local shopCfg = self:getShopCfg(pidData.shop_type, pidData.buy_id)
        -- 购买月卡后刷新
        if shopCfg.shop_type == SHOP_TYPE.monthly_card then
            bee.showUiTask("ShopMonthlyCardEffect", nil, POP_TAG.Reward, LOBBY_POP_PRIORITY.MonthlyCardEffect)
            self:requestPayInfo()
            SignInModel:sendSignIn(0)
        elseif shopCfg.shop_type == SHOP_TYPE.shop_gifts2 and shopCfg.auto_use == 1 then
            for k,v in pairs(data.item_list) do
                if tpl_props[v.item_id].type == GPropKind.OptionalBox then
                    bee.showUiTask("BackpackGift", {id = v.item_id, characterId = self._selectedPledgeRoleId, isAutoSelect = true}, POP_TAG.Reward, LOBBY_POP_PRIORITY.BackpackGift)
                end
            end
        end
    end
    self:setShopPledgeGiftRole()

    -- 恭喜获得
    self:showRewardView(data.item_list)

    bee.emit(EventDef.evt_pay_sucess)
    self:requestShopLimitList()

    if bee.isRelease then
        CS.SdkHelper.SendAdjustRevenueEvent("3e2b4f", pidData.pri_1, "USD")
        CS.SdkHelper.SendFirebaseRevenueEvent(pidData.pri_1, "USD")
        -- SdkHelper:sendFbEvent("fb_mobile_purchase", "fb_currency,USD,fb_mobile_purchase," .. pidData.pri_1)
    end
end

function P:setShopPledgeGiftRole(roleId)
    self._selectedPledgeRoleId = roleId
end

-- =========================== 商城协议 ===========================

-- 获取用户付费数据
function P:requestPayInfo()
    Net:post("player/payInfo", nil, function(data)
        if data.code ~= 0 then
            return
        end

        -- 月卡过期时间戳
        self._monthly_card_exp = data.data.monthly_card_exp
        bee.emit("evt_updateMonthlyCard")
    end)
end

function P:requestReward(shop_type, id)
    local args = {
        shop_type = shop_type,
        id = id,
    }
    Net:post("shop/reward", args, function(data)
        if data.code ~= 0 then
            return
        end

        self:showRewardView(self:getShopRewardList(shop_type, id))
        self:requestShopLimitList()
    end)
end

function P:buyWithProp(shop_type, id, num)
    if not bee.checkCd("shop_purchase", 1) then
        return
    end

    num = num or 1
    local args = {
        shop_type = shop_type,
        id = id,
        num = num or 1,
        mask = "buyWithProp",
    }
    Net:post("shop/buyWithProp", args, function(data)
        if data.code ~= 0 then
            return
        end
        bee.emit("evt_buy_Success", {shop_type = shop_type, id = id})

        local rewards
        if shop_type == SHOP_TYPE.shop_role_skin then
            local shopCfg = SHOP_TYPE_CFG[shop_type][id]
            rewards = {{major_type = GMajorType.ROLE_SKIN, id = shopCfg.role_skin, num = 1}}
        else
            rewards = self:getShopRewardList(shop_type, id)
        end
        for k,v in pairs(rewards) do
            v.num = v.num * num
        end
        self:showRewardView(rewards)

        local cfg = SHOP_TYPE_CFG[shop_type][id]
        if cfg.limit_type and cfg.limit_type ~= 0 then
            self:requestShopLimitList()
        end
        if shop_type == SHOP_TYPE.hot_spring then
            bee.logEvent("onsen-shop_exchange", id, num)
        elseif shop_type == SHOP_TYPE.gala_season then
            bee.logEvent("galaseason-shop_exchange", id, num)
        end
    end)
end

-- 商城限购列表
function P:requestShopLimitList()
    Net:post("shop/limit", {mask = "shopLimit"}, function(data)
        if data.code ~= 0 then
            return
        end

        self._initShopLimitList = true
        self._shopLimitList = {}
        for k, v in pairs(data.list) do
            if not self._shopLimitList[v.shop_type] then
                self._shopLimitList[v.shop_type] = {}
            end
            self._shopLimitList[v.shop_type][v.id] = v
        end
        bee.emit("evt_updateShopLimit")
        self:refreshShopRedPoint()
    end)
end

-- 获取商品价格
function P:requestShopPid()
    Net:post("shop/pid", {avenue_id = G_CHNL_ID}, function(data)
        if data.code ~= 0 then
            return
        end

        self._initShopPid = true
        self._shopPidList = {}
        for k, v in pairs(data.list) do
            self._shopPidList[v.id] = v
        end
        bee.emit("evt_updateShopPid")
    end)
end

-- 获取限购商品已购买次数
function P:getLimitGoodsBoughtCount(shop_type, id)
    if not self._shopLimitList[shop_type] then
        return 0
    end

    if not self._shopLimitList[shop_type][id] then
        return 0
    end

    return self._shopLimitList[shop_type][id].count or 0
end

-- 获取是否有双倍
function P:getIsCanDoubleReward(shop_type, id)
    local cfg = SHOP_TYPE_CFG[shop_type][id]
    if cfg.first_double ~= 1 then
        return false
    end
    if not self._shopLimitList[shop_type] then
        return true
    end
    if not self._shopLimitList[shop_type][id] then
        return true
    end
    return self._shopLimitList[shop_type][id].double == 0
end

-- 是否已领取奖励
function P:getIsClaimReward(shop_type, id)
    if not self._shopLimitList[shop_type] then
        return false
    end
    if not self._shopLimitList[shop_type][id] then
        return false
    end
    return self._shopLimitList[shop_type][id].reward == 0
end

-- =========================== 商城界面配置 ===========================

function P:isShowShopSkin()
    local skinList = self:getShopSkinList()
    if skinList and next(skinList) then
        return true
    end
    return false
end

function P:getShopSideTabs()
    local list = {}
    for k,v in pairs(tpl_shop_page) do
        if v.shop_type == SHOP_TYPE.shop_role_skin then
            if self:isShowShopSkin() then
                table.insert(list, v)
            end
        elseif v.page_type == SHOP_PAGE_TYPE.SIDE and v.is_hide ~= 1 then
            table.insert(list, v)
        end
    end
    table.sort( list, function(a, b) return a.order < b.order end)
    return list
end

function P:getShopSubTabs(id)
    if not tpl_shop_page[id].sub_page then
        return nil
    end

    local list = {}
    for k,v in pairs(tpl_shop_page[id].sub_page) do
        if v == 101 and self:isClaimedFirstRecharge() then
        elseif v == 103 and self:isBoughtIceBreak() then
        elseif tpl_shop_page[v].is_hide ~= 1 then
            if v == 303 then
                local data = self:getShopPackageList(SHOP_TYPE.activity_gifts)
                if next(data) then
                    table.insert(list, tpl_shop_page[v])
                end
            else
                table.insert(list, tpl_shop_page[v])
            end
        end
    end
    table.sort( list, function(a, b) return a.order < b.order end)
    return list 
end

function P:getCurrencyBar(id)
    local list = {}
    local currency_bar = tpl_shop_page[id].currency_bar
    if not currency_bar then
        return list
    end

    for i = 1, #currency_bar, 2 do
        table.insert(list, {id = currency_bar[i], isAdd = currency_bar[i + 1]})
    end
    return list
end

function P:getRewardsListWithType(rewards)
    local list = {}
    for i = 1, #rewards, 3 do
        table.insert(list, {major_type = rewards[i], id = rewards[i + 1], item_id = rewards[i + 1], num = rewards[i + 2]})
    end
    return list
end

function P:getRewardsList(rewards)
    local list = {}
    for i = 1, #rewards, 2 do
        table.insert(list, {major_type = GMajorType.PROP, id = rewards[i], item_id = rewards[i], num = rewards[i + 1]})
    end
    return list
end

function P:getRewardCfg(reward)
    local major_type = reward.major_type or reward[1]
    local id = reward.id or reward[2]
    if major_type == GMajorType.PROP then
        return tpl_props[id]
    elseif major_type == GMajorType.ROLE then
        return tpl_character[id]
    elseif major_type == GMajorType.ROLE_SKIN then
        return tpl_character_skin[id]
    end
end

function P:setShopLimitStr(textNode, limit_type, limit_count, buyCount)
    if limit_type == SHOP_LIMIT_TYPE.DAILY then
		return bee.setText(textNode, _T("LAB_SHOP_COMMON_11") .. ":" .. buyCount .. "/" .. limit_count)
	elseif limit_type == SHOP_LIMIT_TYPE.WEEKLY then
		return bee.setText(textNode, _T("LAB_SHOP_COMMON_12") .. ":" .. buyCount .. "/" .. limit_count)
	elseif limit_type == SHOP_LIMIT_TYPE.MONTHLY then
		return bee.setText(textNode, _T("LAB_SHOP_COMMON_13") .. ":" .. buyCount .. "/" .. limit_count)
	elseif limit_type == SHOP_LIMIT_TYPE.PERMANENT then
		return bee.setText(textNode, _T("LAB_SHOP_COMMON_14") .. ":" .. buyCount .. "/" .. limit_count)
	end
    return bee.setText(textNode, "")
end

-- 皮肤商城
function P:getShopSkinList(isSort)
    local curTime = bee.getServerTime()
    local list = {}
    for k, v in pairs(tpl_shop_role_skin) do
        if self:productIsCanShow(v) and tpl_character_skin[v.role_skin] then
            table.insert(list, {cfg = v, isOwn = CharacterModel:isOwnedSkin(v.role_skin)})
        end
    end
    if isSort then
        table.sort( list, function(a, b)
            local sumA = 1000
            local sumB = 1000
            if a.isOwn then
                sumB = sumB + 100
            end
            if b.isOwn then
                sumA = sumA + 100
            end
            if a.cfg.index < b.cfg.index then
                sumA = sumA + 10
            end
            if a.cfg.index > b.cfg.index then
                sumB = sumB + 10
            end
            if a.cfg.id < b.cfg.id then
                sumA = sumA + 1
            end
            if b.cfg.id < a.cfg.id then
                sumB = sumB + 1
            end
            return sumA > sumB
        end)
    end
    for i,v in ipairs(list) do
        v.index = i
    end
    return list
end

-- 判断皮肤是否在售
function P:getIsInShopSkin(skinId)
    if tpl_shop_page[2].is_hide == 1 then
        return false
    end
    for k,v in pairs(self:getShopSkinList()) do
        if v.cfg.role_skin == skinId then
            return true
        end
    end
    return false
end

-- 获取皮肤上架剩余时间
function P:getShopSkinLeftTime(skinId)
    if tpl_shop_page[2].is_hide == 1 then
        return 0
    end
    for k, v in pairs(self:getShopSkinList()) do
        if v.cfg.role_skin == skinId and v.cfg.time_end then
            return v.cfg.time_end - bee.getServerTime()
        end
    end
    return 0
end

-- 礼包商城
function P:getShopPackageList(shop_type)
    local curTime = bee.getServerTime()
    local list = {}
    local cfg = tpl_shop_gifts
    if shop_type == SHOP_TYPE.activity_gifts then
        cfg = tpl_shop_activity_gifts
    end
    for k, v in pairs(cfg) do
        if self:getPidData(v.buy_id) then
            if v.shop_type == shop_type and self:productIsCanShow(v) then
                local buyCount = self:getLimitGoodsBoughtCount(shop_type, v.id)
                table.insert(list, {cfg = v, soldOut = buyCount == v.limit_count, buyCount = buyCount})
            end
        end
    end
    table.sort( list, function(a, b)
        local sumA = 1000
        local sumB = 1000
        if a.soldOut then
            sumB = sumB + 100
        end
        if b.soldOut then
            sumA = sumA + 100
        end
        if a.cfg.index < b.cfg.index then
            sumA = sumA + 10
        end
        if a.cfg.index > b.cfg.index then
            sumB = sumB + 10
        end
        if a.cfg.id < b.cfg.id then
            sumA = sumA + 1
        end
        if b.cfg.id < a.cfg.id then
            sumB = sumB + 1
        end
        return sumA > sumB
    end)
    return list
end

-- 兑换商城
function P:getShopExchangeList(shop_type)
    local list = {}
    local ownList = {}
    for k, v in pairs(SHOP_TYPE_CFG[shop_type] or tpl_shop_exchange) do
        if v.shop_type == shop_type then
            if self:productIsCanShow(v) then
                local buyCount = self:getLimitGoodsBoughtCount(shop_type, v.id)
                local prop = self:getRewardsListWithType(v.props)[1]
                local isOwn = false
                if prop.major_type == GMajorType.ROLE then
                    isOwn = CharacterModel:getRoleIsOwn(prop.id)
                elseif prop.major_type == GMajorType.ROLE_SKIN then
                    isOwn = CharacterModel:isOwnedSkin(prop.id)
                elseif prop.major_type == GMajorType.PROP then
                    if ItemModel:getGPropType(tpl_props[prop.id].type) == GPropType.Display then
                        isOwn = ItemModel:isOwned(prop.id)
                    end
                end
                local soldOut = buyCount == v.limit_count
                if isOwn or soldOut then
                    table.insert(ownList, {cfg = v, soldOut = soldOut, buyCount = buyCount, isOwn = isOwn})
                else
                    table.insert(list, {cfg = v, soldOut = soldOut, buyCount = buyCount, isOwn = isOwn})
                end
            end
        end
    end
    local echangeSortFunc = function(a, b)
        local sumA = 100000
        local sumB = 100000

        if a.major_type == GMajorType.ROLE_SKIN then
            sumA = sumA + 10000
        elseif a.major_type == GMajorType.ROLE then
            sumA = sumA + 1000
        else
            sumA = sumA + 100
        end
        if b.major_type == GMajorType.ROLE_SKIN then
            sumB = sumB + 10000
        elseif b.major_type == GMajorType.ROLE then
            sumB = sumB + 1000
        else
            sumB = sumB + 100
        end
        if a.cfg.index < b.cfg.index then
            sumA = sumA + 10
        end
        if a.cfg.index > b.cfg.index then
            sumB = sumB + 10
        end
        if a.cfg.id < b.cfg.id then
            sumA = sumA + 1
        end
        if b.cfg.id < a.cfg.id then
            sumB = sumB + 1
        end
        return sumA > sumB
    end
    table.sort(ownList, echangeSortFunc)
    table.sort(list, echangeSortFunc)
    for i,v in ipairs(ownList) do
        table.insert(list, v)
    end
    return list
end

-- 充值商城
function P:getShopTopUpList(shop_type)
    local list = {}
    for k, v in pairs(tpl_shop_recharge) do
        if v.shop_type == shop_type and (v.buy_id == 0 or self:getPidData(v.buy_id)) then
            local soldOut = false
            if v.daily_rewards == 1 then
                soldOut = self:getIsClaimReward(v.shop_type, v.id)
            end
            table.insert(list, {cfg = v, soldOut = soldOut})
        end
    end
    table.sort( list, function(a, b)
        local sumA = 1000
        local sumB = 1000
        if a.soldOut then
            sumB = sumB + 100
        end
        if b.soldOut then
            sumA = sumA + 100
        end
        if a.cfg.index < b.cfg.index then
            sumA = sumA + 10
        end
        if a.cfg.index > b.cfg.index then
            sumB = sumB + 10
        end
        if a.cfg.id < b.cfg.id then
            sumA = sumA + 1
        end
        if b.cfg.id < a.cfg.id then
            sumB = sumB + 1
        end
        return sumA > sumB
    end)
    return list
end

function P:getShopTimeText(dt)
    if dt > 86400 then
        local d = math.floor(dt / 86400)
        local h = math.ceil((dt % 86400) / 3600)
        return _F("LAB_SHOP_COMMON_27", d, h)
    elseif dt > 3600 then
        local h = math.floor(dt / 3600)
        local m = math.ceil((dt % 3600) / 60)
        return _F("LAB_SHOP_COMMON_26", h, m)
    elseif dt == 3600 then
        return _F("LAB_SHOP_COMMON_25", 60)
    else
        local m = math.ceil((dt % 3600) / 60)
        return _F("LAB_SHOP_COMMON_25", m)
    end
end

function P:getShopTimeText2(dt)
    if dt > 60 then
        local m = math.floor((dt % 3600) / 60)
        local s = math.ceil((dt % 3600) % 60)
        return _F("LAB_SHOP_COMMON_40", m, s)
    else
        return _F("LAB_SHOP_COMMON_41", math.ceil(dt))
    end
end

-- 是否可领取首充奖励
function P:isCanGetFirstRechargeReward()
    if not self._shopLimitList[SHOP_TYPE.first_recharge] then
        return false
    end
    if not self._shopLimitList[SHOP_TYPE.first_recharge][1] then
        return false
    end
    return self._shopLimitList[SHOP_TYPE.first_recharge][1].first_recharge == 0
end

-- 是否已领取首充奖励
function P:isClaimedFirstRecharge()
    if not self._shopLimitList[SHOP_TYPE.first_recharge] then
        return false
    end
    if not self._shopLimitList[SHOP_TYPE.first_recharge][1] then
        return false
    end
    return self._shopLimitList[SHOP_TYPE.first_recharge][1].reward == 0
end

-- 是否已购买新会长礼包
function P:isBoughtIceBreak()
    return self:getLimitGoodsBoughtCount(SHOP_TYPE.new_comer, 10001) > 0
end

-- 恭喜获得弹窗
function P:showRewardView(rewards, closeCb)
    if not rewards then
        return
    end

    local showRewardList = {}
    local showNewList = {}
    for i, v in ipairs(rewards) do
        v.num = v.num * (num or 1)
        if v.major_type == GMajorType.ROLE then
            v.new = not CharacterModel:getRole(v.item_id)
            table.insert(showNewList, v)
        elseif v.major_type == GMajorType.ROLE_SKIN then
            v.new = not CharacterModel:isOwnedSkin(v.item_id)
            table.insert(showNewList, v)
        else
            v.new = ItemModel:checkIsNewItem(v.item_id)
            if ItemModel:getGPropType(tpl_props[v.item_id].type) == GPropType.Display then
                if v.new then
                    table.insert(showNewList, v)
                end
            end
        end
        table.insert(showRewardList, v)
    end

    if next(showNewList) then
        bee.showUiTask("GachaResultShow", {showList = showNewList}, POP_TAG.Reward, LOBBY_POP_PRIORITY.RewardNew)
    end
    bee.showUiTask("BackpackClaimResult", {items = showRewardList, cb = closeCb}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)

    bee.runTask(POP_TAG.Reward)
end

function P:refreshShopRedPoint()
    -- 首充奖励红点
    if not self:isClaimedFirstRecharge() and self:isCanGetFirstRechargeReward() then
        if tpl_shop_page[101].is_hide ~= 1 then
            RedManager:addTag(RedTag.FirstRecharge)
        end
    else
        RedManager:removeTag(RedTag.FirstRecharge)
    end

    -- 每日免费奖励红点
    local freeCfg
    for k, v in pairs(tpl_shop_recharge) do
        if v.daily_rewards == 1 then
            freeCfg = v
            break
        end
    end
    local isReward = self:getIsClaimReward(freeCfg.shop_type, freeCfg.id)
    if isReward then
        RedManager:removeTag(RedTag.DailyFree)
    else
        RedManager:addTag(RedTag.DailyFree)
    end

    self:refreshShopNewOutTag()
end

function P:refreshShopNewOutTag()
    -- 主界面商城红点，优先显示圆点，再显示上新
    if RedManager:isTag(RedTag.Shop) then
        RedManager:removeTag(RedTag.ShopNewOut)
        RedManager:removeTag(RedTag.ShopTimeLimitOut)
    elseif RedManager:isTag(RedTag.ShopNew) then
        RedManager:addTag(RedTag.ShopNewOut)
        RedManager:removeTag(RedTag.ShopTimeLimitOut)
    elseif RedManager:isTag(RedTag.ShopTimeLimit) then
        RedManager:addTag(RedTag.ShopTimeLimitOut)
    else
        RedManager:removeTag(RedTag.ShopNewOut)
        RedManager:removeTag(RedTag.ShopTimeLimitOut)
    end
end

-- 上新标记
function P:refreshShopNewTag(shop_type)
    if not shop_type or shop_type == 11 or shop_type == 12 or shop_type == 13 or shop_type == 14 or shop_type == 18 then
        self:refreshShopDecorationRedTag()
    end
    if not shop_type or shop_type == 3 then
        self:refreshShopSkinRedTag()
    end
    self:refreshShopNewOutTag()
end

function P:getShopTypePageIsHide(shop_type)
    for k,v in pairs(tpl_shop_page) do
        if v.shop_type == shop_type then
            return v.is_hide == 1
        end
    end
    return false
end

-- 装饰上新红点
function P:refreshShopDecorationRedTag()
    local curTime = bee.getServerTime()
    -- 主题商店
    local themeTag = false
    local themeTimeLimitTag = false
    for k, v in pairs(self:getThemeList(true)) do
        local isOwn = self:getThemeIsOwn(v.id)
        -- 上新红点
        if isOwn then
            if not self:isInNewItems(v) then
                self:setNewItem(v)
            end
        elseif v.new_tag == 1 then
            if not self._newitems[SHOP_TYPE.shop_theme] then
                themeTag = true
            else
                local isIn = self:isInNewItems(v)
                if not isIn then
                    themeTag = true
                end
            end
        end
        -- 限时红点
        if not self._timeLimitItems[v.shop_type] then
            self._timeLimitItems[v.shop_type] = {}
        end
        if v.time_end and not isOwn then
            if v.time_end - curTime <= 259200 then
                if self._timeLimitItems[v.shop_type][v.id] ~= 1 then
                    themeTimeLimitTag = true
                end
            else
                self._timeLimitItems[v.shop_type][v.id] = 0
            end
        else
            self._timeLimitItems[v.shop_type][v.id] = 0
        end
    end
    if themeTag then
        RedManager:addTag(RedTag.DecorateNew, SHOP_TYPE.shop_theme)
        RedManager:removeTag(RedTag.DecorateTimeLimit, SHOP_TYPE.shop_theme)
    elseif themeTimeLimitTag then
        RedManager:removeTag(RedTag.DecorateNew, SHOP_TYPE.shop_theme)
        RedManager:addTag(RedTag.DecorateTimeLimit, SHOP_TYPE.shop_theme)
    else
        RedManager:removeTag(RedTag.DecorateNew, SHOP_TYPE.shop_theme)
        RedManager:removeTag(RedTag.DecorateTimeLimit, SHOP_TYPE.shop_theme)
    end

    -- 装饰商店
    local decorateTag = {}
    local decorateTimeLimitTag = {}
    for k,v in pairs(tpl_shop_decoration) do
        if decorateTag[v.shop_type] == nil then
            decorateTag[v.shop_type] = false
        end
        local isCanShow = self:productIsCanShow(v)
        if isCanShow then
            -- 上新红点
            local isOwn = ItemModel:getItem(v.props[1])
            if isOwn then
                if not self:isInNewItems(v) then
                    self:setNewItem(v)
                end
            elseif v.new_tag == 1 then
                if not self._newitems[v.shop_type] then
                    decorateTag[v.shop_type] = true
                elseif not decorateTag[v.shop_type] then
                    local isIn = self:isInNewItems(v)
                    if not isIn then
                        decorateTag[v.shop_type] = true
                    end
                end
            end
            -- 限时红点
            if not self._timeLimitItems[v.shop_type] then
                self._timeLimitItems[v.shop_type] = {}
            end
            if v.time_end and isCanShow then
                if v.time_end - curTime <= 259200 then
                    if self._timeLimitItems[v.shop_type][v.id] ~= 1 then
                        decorateTimeLimitTag[v.shop_type] = true
                    end
                else
                    self._timeLimitItems[v.shop_type][v.id] = 1
                end
            else
                self._timeLimitItems[v.shop_type][v.id] = 0
            end
        end
    end
    for k, v in pairs(decorateTag) do
        if v then
            RedManager:addTag(RedTag.DecorateNew, k)
            RedManager:removeTag(RedTag.DecorateTimeLimit, k)
        elseif decorateTimeLimitTag[k] then
            RedManager:removeTag(RedTag.DecorateNew, k)
            RedManager:addTag(RedTag.DecorateTimeLimit, k)
        else
            RedManager:removeTag(RedTag.DecorateNew, k)
            RedManager:removeTag(RedTag.DecorateTimeLimit, k)
        end
    end

    self:_refreshTimeLimitItems()
end

-- 服饰上新红点
function P:refreshShopSkinRedTag()
    if not self:isShowShopSkin() then
        RedManager:removeTag(RedTag.SkinNew)
        return
    end
    -- 服饰商店
    local skinRedTag = false
    local skinTimeLimitTag = false
    local curTime = bee.getServerTime()
    for k,v in pairs(self:getShopSkinList()) do
        local isOwn = CharacterModel:isOwnedSkin(v.cfg.role_skin)
        -- 新标签
        if isOwn then
            if not self:isInNewItems(v.cfg) then
                self:setNewItem(v.cfg, true)
            end
        elseif v.cfg.new_tag == 1 then
            if not self._newitems[SHOP_TYPE.shop_role_skin] then
                skinRedTag = true
                break
            end
            local isIn = self:isInNewItems(v.cfg)
            if not isIn then
                skinRedTag = true
            end
        end
        -- 限时标签
        if not self._timeLimitItems[v.cfg.shop_type] then
            self._timeLimitItems[v.cfg.shop_type] = {}
        end
        if v.cfg.time_end and not isOwn then
            if v.cfg.time_end - curTime <= 259200 then
                if self._timeLimitItems[v.cfg.shop_type][v.cfg.id] ~= 1 then
                    skinTimeLimitTag = true
                end
            else
                self._timeLimitItems[v.cfg.shop_type][v.cfg.id] = 0
            end
        else
            self._timeLimitItems[v.cfg.shop_type][v.cfg.id] = 0
        end
    end
    if skinRedTag then
        RedManager:addTag(RedTag.SkinNew)
        RedManager:removeTag(RedTag.SkinTimeLimit)
    elseif skinTimeLimitTag then
        RedManager:removeTag(RedTag.SkinNew)
        RedManager:addTag(RedTag.SkinTimeLimit)
    else
        RedManager:removeTag(RedTag.SkinNew)
        RedManager:removeTag(RedTag.SkinTimeLimit)
    end

    self:_refreshTimeLimitItems()
end

function P:_refreshTimeLimitItems()
    local list = {}
    for shop_type, v in pairs(self._timeLimitItems) do
        for id, tag in pairs(v) do
            if tag == 1 then
                table.insert(list, {shop_type, id})
            end
        end
    end
    self.cloud["timeLimitItems" .. PlayerModel:getUid()] = list
    self:onSave()
end

function P:isShowNewTag(cfg)
    if cfg.new_tag ~= 1 then
        return false
    end
    if not self._newitems[cfg.shop_type] then
        return true
    end
    local isIn = self:isInNewItems(cfg)
    return not isIn
end

function P:isInNewItems(cfg)
    if not self._newitems[cfg.shop_type] then
        self._newitems[cfg.shop_type] = {}
    end
    local isIn = false
    for _, checkId in pairs(self._newitems[cfg.shop_type]) do
        if cfg.id == checkId then
            isIn = true
            break
        end
    end
    return isIn
end

function P:setNewItem(cfg, notRefresh)
    if not self._newitems[cfg.shop_type] then
        self._newitems[cfg.shop_type] = {}
    end
    local isIn = false
    for _, checkId in pairs(self._newitems[cfg.shop_type]) do
        if cfg.id == checkId then
            isIn = true
            break
        end
    end
    if not isIn then
        table.insert(self._newitems[cfg.shop_type], cfg.id)
        table.insert(self.cloud["newitems" .. PlayerModel:getUid()], {cfg.shop_type, cfg.id})
    end
    self:onSave()
    if not notRefresh then
        self:refreshShopNewTag(cfg.shop_type)
    end
end

function P:refreshTimeLimitItemByShopType(shop_type, notRefresh)
    for k, v in pairs(SHOP_TYPE_CFG[shop_type]) do
        if self:productIsCanShow(v) and v.shop_type == shop_type then
            if not self._timeLimitItems[shop_type] then
                self._timeLimitItems[shop_type] = {}
            end
            self._timeLimitItems[shop_type][v.id] = 1
        end
    end

    self:_refreshTimeLimitItems()
    if not notRefresh then
        self:refreshShopNewTag(shop_type)
    end
end

function P:refreshNewItemByShopType(shop_type, notRefresh)
    for k, v in pairs(SHOP_TYPE_CFG[shop_type]) do
        if self:productIsCanShow(v) and v.shop_type == shop_type and v.new_tag == 1 then
            self:setNewItem(v, notRefresh)
        end
    end
end

function P:getShopRewardList(shop_type, id)
    local cfg = SHOP_TYPE_CFG[shop_type][tonumber(id)]
    if shop_type == SHOP_TYPE.shop_exchange or SHOP_TYPE_CFG[shop_type] == tpl_shop_exchange or SHOP_TYPE_CFG[shop_type] == tpl_shop_activity then
        return self:getRewardsListWithType(cfg.props)
    elseif shop_type == SHOP_TYPE.first_recharge then
        return self:getRewardsListWithType(cfg.rewards)
    elseif shop_type == SHOP_TYPE.shop_theme then
        local list = {}
        local cfg = tpl_shop_theme[id]
        for i = 2, #cfg.props, 2 do
            if not ItemModel:getItem(tpl_shop_decoration[cfg.props[i]].props[1]) then
                table.insert(list, tpl_shop_decoration[cfg.props[i]].props[1])
                table.insert(list, tpl_shop_decoration[cfg.props[i]].props[2])
            end
        end
        return self:getRewardsList(list)
    else
        return self:getRewardsList(cfg.props)
    end
end

-- =========================== 月卡 ===========================

function P:setMonthlyCardLeftTime(t)
    self._monthly_card_exp = t
end

-- 获取月卡过期时间
function P:getMonthlyCardLeftTime()
    if not self._monthly_card_exp then
        return 0
    end
    return self._monthly_card_exp - bee.getServerTime()
end

-- 是否有月卡
function P:isMonthlyCard()
    return self:getMonthlyCardLeftTime() > 0
end

-- 获取月卡签到奖励
function P:getMonthlyCardSignInRewards()
    return self:getRewardsList(tpl_constdata.Monthly_Card_Daily_Rewards)
end

-- =========================== 装饰商城 ===========================

-- 主题列表
function P:getThemeList(notSort)
    local curTime = bee.getServerTime()
    local list = {}
    for k, v in pairs(tpl_shop_theme) do
        if self:productIsCanShow(v) then
            local temp = {}
            -- 拷贝原配置
            for k1, v1 in pairs(v) do
                temp[k1] = v1
            end
            -- 获取礼包道具，计算价格
            temp.items = {}
            temp.oriPri = 0
            temp.isOwn = true
            for i = 2, #v.props, 2 do
                local cfg = tpl_shop_decoration[v.props[i]]
                local isOwn = ItemModel:getItem(cfg.props[1])
                temp.consumeId = cfg.pri[1]
                if not isOwn then
                    temp.oriPri = temp.oriPri + cfg.pri[2]
                    temp.isOwn = false
                end
                table.insert(temp.items, {cfg = tpl_props[cfg.props[1]], isOwn = isOwn})
            end
            temp.pri = math.floor(temp.oriPri * (temp.discount / 1000) + 0.5)
            table.insert(list, temp)
        end
    end
    if not notSort then
        table.sort( list, function(a, b)
            local sumA = 1000
            local sumB = 1000
            if a.isOwn then
                sumB = sumB + 100
            end
            if b.isOwn then
                sumA = sumA + 100
            end
            if a.index < b.index then
                sumA = sumA + 10
            end
            if a.index > b.index then
                sumB = sumB + 10
            end
            if a.id < b.id then
                sumA = sumA + 1
            end
            if b.id < a.id then
                sumB = sumB + 1
            end
            return sumA > sumB
        end)
    end
    return list
end

function P:getDecorateList(shop_type, propType, isSort)
    local curTime = bee.getServerTime()
    local list = {}
    for k, v in pairs(tpl_shop_decoration) do
        if self:productIsCanShow(v) and (v.shop_type == shop_type or not shop_type) then
            if propType then
                local propCfg = tpl_props[v.props[1]]
                if propCfg.type == propType then
                    table.insert(list, {cfg = v, isOwn = ItemModel:getItem(v.props[1])})
                end
            else
                table.insert(list, {cfg = v, isOwn = ItemModel:getItem(v.props[1])})
            end
        end
    end
    if isSort then
        table.sort( list, function(a, b)
            local sumA = 1000
            local sumB = 1000
            if a.isOwn then
                sumB = sumB + 100
            end
            if b.isOwn then
                sumA = sumA + 100
            end
            if a.cfg.index < b.cfg.index then
                sumA = sumA + 10
            end
            if a.cfg.index > b.cfg.index then
                sumB = sumB + 10
            end
            if a.cfg.id < b.cfg.id then
                sumA = sumA + 1
            end
            if b.cfg.id < a.cfg.id then
                sumB = sumB + 1
            end
            return sumA > sumB
        end)
    end
    return list
end

-- 判断主题是否已拥有
function P:getThemeIsOwn(id)
    local cfg = tpl_shop_theme[id]
    for i = 2, #cfg.props, 2 do
        local propCfg = tpl_shop_decoration[cfg.props[i]]
        local isOwn = ItemModel:getItem(propCfg.props[1])
        if not isOwn then
            return false
        end
    end
    return true
end

-- 判断主题是否上架中
function P:getThemeIsCanBuy(id)
    local cfg = tpl_shop_theme[id]
    return self:productIsCanShow(cfg)
end

-- 判断该装饰是否在主题礼包中
function P:getItemIsInThemePackage(item_id)
    for k, theme in pairs(tpl_shop_theme) do
        for i = 2, #theme.props, 2 do
            local cfg = tpl_shop_decoration[theme.props[i]]
            if cfg.props[1] == item_id then
                if self:getThemeIsCanBuy(cfg.relation_gift[2]) then
                    return cfg.relation_gift[2]
                end
            end
        end
    end
    return false
end

-- 获取装饰配置
function P:getDecorateShopCfgById(item_id)
    for k, v in pairs(tpl_shop_decoration) do
        if item_id == v.props[1] then
            return v
        end
    end
end

-- 是否有誓约直通礼包
function P:getCharacterGiftCfg(characterId)
    for k,v in pairs(tpl_gifts_character) do
        if v.id == characterId then
            return v, SHOP_TYPE_CFG[v.gifts_id[1]][v.gifts_id[2]]
        end
    end
end

-- 是否自动弹出契约礼包
function P:autoShowCharacterGift(characterId)
    -- if not CharacterModel:getRole(characterId) then
    --     return false
    -- end
    -- if not self:getCharacterGiftCfg(characterId) then
    --     return false
    -- end
    -- if self._isAutoShowCharacterGift then
    --     return false
    -- end

    -- if CharacterModel:getLeftGiftCnt() == 0 then
    --     self._isAutoShowCharacterGift = true
    --     UiManager:showUI("ShopPledgeExpress", {id = characterId})
    --     return true
    -- end

    -- local giftList = ItemModel:getAllShowItems(2)
    -- for k, v in pairs(giftList) do
    --     if v.num > 0 then
    --         return false
    --     end
    -- end

    -- self._isAutoShowCharacterGift = true
    -- UiManager:showUI("ShopPledgeExpress", {id = characterId})
    -- return true
    return false
end

function P:getShopPushList()
    local list = {}

    -- 首充
    if not self:isClaimedFirstRecharge() then
        table.insert(list, {view = "views/Shop/ShopFirstRecharge", pos = bee.v3(0, 0, 0)})
    end
    -- 破冰礼包
    if not self:isBoughtIceBreak() then
        table.insert(list, {view = "views/Shop/ShopNewComerExclusive", pos = bee.v3(0, 0, 0)})
    end

    return list
end

-- 是否可推送新人特惠弹窗
function P:isShowShopPush()
    -- 本次登录已推送
    if self._isShowShopPush then
        return
    end
    -- 今日已推送
    if not LocalStore:isDailyTagValidCrossDay("shop_push" .. PlayerModel:getUid()) then
        return
    end
    return #self:getShopPushList() > 0
end

-- 记录自动推送新人优惠弹窗
function P:recordAutoShowShopPush()
    self._isShowShopPush = true
end

function P:evt_payFail()
    self:doPayFail()
end

function P:evt_payFinished()
    self:doPaySuc()
end

function P:getPriText(pidCfg)
    if G_CHNL_ID == 5 or G_CHNL_ID == 6 then
        local info = PayHelper:getProductInfo(pidCfg.pid)
        local priStr = pidCfg.pri_1
        return info and info.pri or ("USD " .. pidCfg.pri_1)
    else
        if not self._shopPidList then
            self:initInfo()
            return tpl_shop_cur_type[PlayerModel:getCurId()].code .. " " .. pidCfg["pri_" .. PlayerModel:getCurId()]
        else
            return tpl_shop_cur_type[PlayerModel:getCurId()].code .. " " .. self._shopPidList[pidCfg.id]["pri_" .. PlayerModel:getCurId()]
        end
    end
end

function P:evt_serverTimeCrossDay()
	bee.once(math.random(1, 60), function()
        self:requestShopLimitList()
    end)
end

-- 判断商品是否可显示
function P:productIsCanShow(cfg)
    if not cfg then
        return false
    end
    if self:getShopTypePageIsHide(cfg.shop_type) then
        return false
    end
    local curTime = bee.getServerTime()
    local isCanShow = true
    if cfg.time_start or cfg.time_end then
        if cfg.time_start and cfg.time_end then
            isCanShow = (curTime >= cfg.time_start or PlayerModel:isEventWhite()) and (curTime <= cfg.time_end)
        elseif cfg.time_start then
            isCanShow = curTime >= cfg.time_start or PlayerModel:isEventWhite()
        elseif cfg.time_end then
            isCanShow = curTime <= cfg.time_end
        end
    elseif cfg.activity and cfg.activity > 0 then
        if cfg.activity == 20001 then
            isCanShow = SpringFestivalModel:isActivityOpen()
        else
            isCanShow = ActivityManager:isActivityOpen(ActivityId.Theme, cfg.activity)
        end
    end
    return isCanShow
end

function P:tryAutoPop()
    -- 活动礼包
    local data = ShopModel:getShopPackageList(SHOP_TYPE.activity_gifts)
    for k, v in pairs(data) do
        if not v.soldOut then
            local activityId = ThemeModel:getConfId()
            if activityId == ActivityId.BunnyGirl then
                if LocalStore:isDailyTagValidCrossDay("activity_packet_push" .. PlayerModel:getUid()) then
                    bee.showUiTask("BunnyGirlPackage", nil, nil, LOBBY_POP_PRIORITY.ActivityGift)
                    return
                end
            end
        end
    end
end

-- 是否为复刻皮肤
function P:isRerunSkin(skinId)
    for k, v in pairs(self:getShopSkinList()) do
        if v.cfg.role_skin == skinId then
            return v.cfg.is_rerun == 1
        end
    end
    return false
end

return P