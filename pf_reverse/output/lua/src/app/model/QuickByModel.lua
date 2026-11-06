local P = class("QuickByModel", BaseModel)
QuickByModel = P

function P:ctor()
    P.super.ctor(self)

    --#region 快速补码
    self.curLv = 0
    self.endTime = 0

    self.inLobby = false
    self.btnDic = {}
    self.tag = nil
    --#endregion

    --#region 超值礼包
    self.limit_gift_id = 0
    self.limit_endTime = 0

    self.limit_btnDic = {}

    self.limit_isLogin = false
    self.limit_tag = nil

    self.popupData = nil
    self.popupSign = false
    --#endregion
end

function P:afterInit()
end

--#region 快速补码

function P:addButtonItem(uiName, object)
    if bee.isNull(object) then
        return
    end

    local item = {}
    item.go = object
    item.time = object.transform:Find("CountDown/Text")
    bee.addClick(item.go, function()
        self:showView()
    end)
    self.btnDic[uiName] = item
    
    if self.endTime > 0 then
        item.go.gameObject:SetActive(true)
        -- item.go:GetComponent("Animator"):Play("UI_1_QuickByButton_into")
        bee.setText(item.time, ShopModel:getShopTimeText2(self.endTime - bee.getServerTime()))
    else
        item.go.gameObject:SetActive(false)
    end

    self:switchBtns()
end

function P:setData(lv, time)
    self.curLv = lv or 0
    self.endTime = time or 0
end

--进入主界面、局内桌面触发
function P:requireData()
    self.inLobby = true
    Net:sendReq("pb.PushGiftREQ", {
        from_game_type = bee.isInHome() and 0 or 1,
        lvl = 0,
        game_type = 0,
    })
end

--UI主动触发
function P:checkShowView(gameType)
    if os.time() < self.endTime then
        self:showView(self.curLv, gameType)
    else
        if not bee.isInGame() then
            --筹码获得途径
            UiManager:showUI("BackpackDetail", {data = ItemModel:getItem(GPropId.Gold, true)})
        end
    end
end

--局内触发被动
function P:checkInsideGame(gameType, qbId)
    if not self:checkRequestable(qbId) then
        return
    end

    Net:sendReq("pb.PushGiftREQ", {
        from_game_type = bee.isInHome() and 0 or 1,
        lvl = qbId,
        game_type = gameType,
    })
end

--休闲游戏被动触发
function P:checkSideGame(sign, sum, gameType, lvlId)
	if not sign then
		return
	end

    if sum <= 0 then
        local cfg
        if gameType == GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME then
            cfg = tpl_color_game[lvlId]
        elseif gameType == GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME then
            cfg = tpl_pinball[lvlId]
        end
        if cfg then
            if not self:checkRequestable(cfg.quick_buy) then
                return
            end

            if PlayerModel:getGold() < cfg.push_balance then
                Net:sendReq("pb.PushGiftREQ", {
                    from_game_type = bee.isInHome() and 0 or 1,
                    lvl = lvlId,
                    game_type = gameType,
                })
            end
        end
    end
end

--推送检测
function P:checkRequestable(lv)
    return lv > self.curLv
end


function P:evt_PushGiftRSP(msg)
    if msg.code == 0 then
        self:setData(msg.gift_id, msg.end_time)
        if msg.end_time <= 0 then
            self:clearTime()
        else
            self:showButtons()
            if not self.inLobby then
                self:showView(msg.gift_id, msg.game_type)
            end
        end

        if self.inLobby then
            self.inLobby = false
        end
    end
end

function P:showButtons()
    for k,v in pairs(self.btnDic) do
        if bee.isNull(v.go) then
            self.btnDic[k] = nil
        else
            v.go:SetActive(true)
            -- v.go:GetComponent("Animator"):Play("UI_1_QuickByButton_into")
            bee.setText(v.time, ShopModel:getShopTimeText2(self.endTime - bee.getServerTime()))
        end
    end
    self:countDown()
    self:switchBtns()
end
function P:hideButton(obj)
    if obj.activeSelf then
        obj:GetComponent("Animator"):Play("UI_1_QuickByButton_back")
    end
    for k,v in pairs(self.btnDic) do
        if v.go == obj then
            self.btnDic[k] = nil
        end
    end
end
function P:hideButtons()
    for k,v in pairs(self.btnDic) do
        if bee.isNull(v.go) then
            self.btnDic[k] = nil
        else
            v.go:SetActive(false)
        end
    end
    -- self.btnDic = {}
    scheduler:removeTag(self.tag)
    self.tag = nil
end
function P:updateButtons(retime)
    for k,v in pairs(self.btnDic) do
        if bee.isNull(v.go) then
            self.btnDic[k] = nil
            self:switchBtns()
        else
            bee.setText(v.time, ShopModel:getShopTimeText2(retime))
        end
    end
end

function P:switchBtns()
    local sideGameItem = self.btnDic["SideGameView"]
    local insideGameItem = self.btnDic["PKUILayer"]
    if sideGameItem and insideGameItem and not bee.isNull(sideGameItem.go) then
        sideGameItem.go:SetActive(false)
    end
end

function P:showView(lv, gameType)
    local data = {quick_buy = lv or self.curLv, gameType = gameType or 0}
    if tpl_quick_purchase[data.quick_buy] then
        UiManager:showUI("IngameQuickBy", {data = data, dt = self.endTime - bee.getServerTime()})
    end
end

function P:countDown()
    if self.tag ~= nil then
        return
    end

    local retime = 0
    self.tag = bee.schedule(1, function ()
        retime = self.endTime - bee.getServerTime()
        if retime > 0 then
            self:updateButtons(retime)
        else
            self:clearTime()
        end
    end)
end

function P:clearGift()
    Net:sendReq("pb.PushGiftREQ", {
        from_game_type = bee.isInHome() and 0 or 1,
        lvl = 0,
        game_type = 1,
    })
end

function P:clearTime()
    self.curLv = 0
    self.endTime = 0
    self:hideButtons()
end

--#endregion

--#region 超值礼包

--请求礼包
function P:reqLimitPack()
    self.limit_isLogin = true
    self.popupSign = false
    Net:sendReq("pb.PushRoomGiftREQ", {})
end

function P:evt_PushRoomGiftRSP(msg)
    self:limitClearTime()
    if next(msg) == nil or msg == nil or (msg and msg.code ~= 0) then
        if self.limit_isLogin then
            self.limit_isLogin = false
        end
        return
    end
    if msg.end_time < bee.getServerTime() then
        return
    end

    self.limit_gift_id = msg.gift_id
    self.limit_endTime = msg.end_time
    self:showLimitButtons()

    if self.limit_isLogin then
        self.limit_isLogin = false
        return
    end

    self.popupData = {push = true, gameType = msg.game_type}
    if self.popupSign then
        self.popupSign = false
        bee.checkShowUI("ShopLimitedPackage", self.popupData, nil, LOBBY_POP_PRIORITY.LimitedPack)
    end
end

function P:addLimitButtonItem(uiName, object)
    if bee.isNull(object) then
        return
    end

    local item = {}
    item.go = object
    item.time = object.transform:Find("CountDown/Text")
    bee.addClick(item.go, function()
        UiManager:showUI("ShopLimitedPackage")
    end)
    self.limit_btnDic[uiName] = item
    
    if self.limit_endTime > 0 then
        item.go.gameObject:SetActive(true)
        bee.setText(item.time, ShopModel:getShopTimeText2(self.limit_endTime - bee.getServerTime()))
    else
        item.go.gameObject:SetActive(false)
    end
end

function P:limitCountDown()
    if self.limit_tag ~= nil then
        return
    end

    local retime = 0
    self.limit_tag = bee.schedule(1, function ()
        retime = self.limit_endTime - bee.getServerTime()
        if retime > 0 then
            self:updateLimitButtons(retime)
        else
            self:limitClearTime()
        end
    end)
end

function P:updateLimitButtons(retime)
    for k,v in pairs(self.limit_btnDic) do
        if bee.isNull(v.go) then
            self.limit_btnDic[k] = nil
        else
            bee.setText(v.time, ShopModel:getShopTimeText2(retime))
        end
    end
end

function P:showLimitButtons()
    for k,v in pairs(self.limit_btnDic) do
        if bee.isNull(v.go) then
            self.limit_btnDic[k] = nil
        else
            v.go:SetActive(true)
            bee.setText(v.time, ShopModel:getShopTimeText2(self.limit_endTime - bee.getServerTime()))
        end
    end
    self:limitCountDown()
end

function P:limitClearTime()
    self.limit_gift_id = 0
    self.limit_endTime = 0
    self:hideLimitButtons()
end

function P:hideLimitButton(obj)
    if obj.activeSelf then
        obj:GetComponent("Animator"):Play("UI_1_LimitPackageButton_back")
    end
    for k,v in pairs(self.limit_btnDic) do
        if v.go == obj then
            self.limit_btnDic[k] = nil
        end
    end
end

function P:hideLimitButtons()
    for k,v in pairs(self.limit_btnDic) do
        if bee.isNull(v.go) then
            self.limit_btnDic[k] = nil
        else
            v.go:SetActive(false)
        end
    end
    scheduler:removeTag(self.limit_tag)
    self.limit_tag = nil
end

function P:checkLimitPop()
    if self.popupData then
        bee.showUiTask("ShopLimitedPackage", self.popupData, nil, LOBBY_POP_PRIORITY.LimitedPack)
        self.popupData = nil
    else
        self.popupSign = true
    end
end

--#endregion

return P