local P = class("QuickByModel", BaseModel)
QuickByModel = P

function P:ctor()
    P.super.ctor(self)

    self.curLv = 0
    self.endTime = 0

    self.inLobby = false
    self.btnDic = {}
    self.tag = nil
end

function P:afterInit()
end

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

return P