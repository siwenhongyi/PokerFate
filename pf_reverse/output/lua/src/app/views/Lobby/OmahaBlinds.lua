local P = class("OmahaBlinds", UiFullView)

local SYS_GUIDES = {
    [GAME_GAME_TYPE.LOBBY_HOLDEM_GAME] = 12001,
    [GAME_GAME_TYPE.LOBBY_OMAHA_GAME] = 13001,
}

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
    self.Center = self:find("AnimRoot/Center")
    self.LeftTop = self:find("AnimRoot/LeftTop")
    self.RightTop = self:find("AnimRoot/RightTop")
    self.LeftBottom = self:find("AnimRoot/LeftBottom")
    self.TextGold = self:find("Ticket/CountText", self.RightTop)
    self.QuickByButton = self:find("QuickByButton", self.RightTop)

    self.blinds_title_omaha = self:find("blinds_title_poker/blinds_title_omaha", self.Center)
    self.blinds_title_poker = self:find("blinds_title_poker/blinds_title_poker", self.Center)

    self.RoomList = self:find("RoomList", self.Center)
    self.RoomView = self:find("RoomView", self.Center)
    self.Items = {
        [0] = self:find("Item0", self.Center),
        self:find("Item1", self.Center),
        self:find("Item2", self.Center),
        self:find("Item3", self.Center),
        self:find("Item4", self.Center),
        self:find("Item5", self.Center),
    }
    for _, v in pairs(self.Items) do
        v:SetActive(false)
    end
    bee.addClick(self:find("Ticket", self.RightTop), function()
        Game:playSound("ui_button_confirm")
        ItemModel:jumpViewByItemId(GPropId.Gold)
    end)
    bee.addClick(self:find("Ticket/Icon", self.RightTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(GPropId.Gold, true), target = self:find("Ticket/Icon", self.RightTop)})
    end)
    bee.addClick(self:find("InfoButton", self.LeftTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("IngameRules", {gameType = self._gameType})
        bee.logEvent("ingame-table-rules", self._gameType)
    end)
    bee.addClick(self:find("CloseButton", self.LeftTop), function()
        local View = self:find("Viewport/Content", self.RoomList)
        self.animator.enabled = true
        View:GetComponent("HorizontalLayoutGroup").enabled = true
        View:GetComponent("ContentSizeFitter").enabled = true
        self:hideUI()
    end)
    self.BgImgs = {
        "Blinds[blinds_bg01]",
        "Blinds[blinds_bg02]",
        "Blinds[blinds_bg03]",
        "Blinds[blinds_bg04]",
        "Blinds[blinds_bg05]",
    }
end

function P:onShow()
    if not self._gameType then
        self._gameType = self._params and self._params.gameType or GAME_GAME_TYPE.LOBBY_HOLDEM_GAME
    end
    GameModel.selectRoomGameType = self._gameType
    if self._params and self._params.jump and self._params.jump.select then
        self._gameType = self._params.jump.select
    end
    if self.blinds_title_poker then
        if GF.isOmahaGame(self._gameType) then
            self.blinds_title_omaha:SetActive(true)
            self.blinds_title_poker:SetActive(false)
        else
            self.blinds_title_omaha:SetActive(false)
            self.blinds_title_poker:SetActive(true)
        end
    end
    self._datas = GF.getTableDatas(self._gameType)
    for k, v in ipairs(self._datas) do
        v.index = k
    end
    local w = #self._datas * self.Items[1].transform.sizeDelta.x + (#self._datas - 1) * 30

    local View = self.RoomView
    local isMoved = false
    if SCREEN_WIDTH < w then
        View = self:find("Viewport/Content", self.RoomList)

        if #self._datas >= 4 then
            for i = #self._datas, 4, -1 do
                if SettingModel:isSysUnlockAnim(self._datas[i].unlock_id, true) then
                    isMoved = true
                    break
                end
            end
        end
    end
    self._curStep = 0
    for i = #self._datas, 1, -1 do
        if PlayerModel:getGold() >= self._datas[i].recommend and (not self._datas[i].level_limit or self._datas[i].level_limit <= PlayerModel:getCurLevel()) then
            self._curStep = i
            break
        end
    end
    self._lastSelectIndex = self._curStep

    self.CurItems = {}
    for k, v in ipairs(self._datas) do
        local item 
        if self._gameType == GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN then
            item = self.Items[k]
        else
            item = self.Items[v.bg_color] or CU.GameObject.Instantiate(self.Items[#self.Items])
        end
        item:SetActive(true)
        if k > 1 then
            self:find("Root", item):SetActive(false)
        end
        if View then
            item.transform:SetParent(View.transform, false)
        end
        self:refreshItem(v, item)
        table.insert(self.CurItems, item)
    end
    bee.setTextGold(self.TextGold, _N(PlayerModel:getGold()))
    if GuideManager:isInGuide() then
        self:once(1, function()
            self.animator.enabled = false
            View:GetComponent("HorizontalLayoutGroup").enabled = false
            View:GetComponent("ContentSizeFitter").enabled = false
        end)
    elseif GF.isTrainingGame(self._datas[1].gameType) and not GuideManager:isInGuide() and GuideManager:isSysGuideValid(SYS_GUIDES[self._gameType]) ~= 0 then
        self:once(1, function()
            self.animator.enabled = false
            View:GetComponent("HorizontalLayoutGroup").enabled = false
            View:GetComponent("ContentSizeFitter").enabled = false
        end)
        if SCREEN_WIDTH < w then
            self._horizontalNormalizedPosition = 1
        end
    else
        if SCREEN_WIDTH < w then
            if not isMoved then
                if self._curStep >= 4 then
                    self.RoomList:GetComponent("ScrollRect").horizontalNormalizedPosition = 1
                elseif self._curStep == 3 then
                    self.RoomList:GetComponent("ScrollRect").horizontalNormalizedPosition = 0.5
                end
            else
                self.RoomList:GetComponent("ScrollRect").horizontalNormalizedPosition = 1
            end
        end
    end

    Net:sendReq("pb.RoomWinnerRewardsInfoREQ", {
        game_type = self._gameType,
    })
    if self._datas[1].gameType ~= self._gameType then
        Net:sendReq("pb.RoomWinnerRewardsInfoREQ", {
            game_type = self._datas[1].gameType,
        })
    end
    self:repeatN(#self._datas - 1, 0.08, function(dt, t)
        self:find("Root", self.CurItems[#self._datas - t.num]):SetActive(true)
    end)

    if ThemeModel:isHaveAddtion(self._gameType) and not self:find("HotSpringAddition", self.LeftBottom) and bee.isNull(self.HotSpringAddition) then
        local obj = ThemeModel:createAddtionButton()
        if not bee.isNull(obj) then
            obj.transform:SetParent(self.LeftBottom.transform, false)
            obj.transform.localPosition = bee.v3(-78, -122)
            self.HotSpringAddition = obj
            if View then
                local pos = View.transform.localPosition
                pos.y = pos.y + 63
                View.transform.localPosition = pos

                if self.blinds_title_poker then
                    self.blinds_title_omaha.transform.localPosition = bee.v3(0, 25)
                    self.blinds_title_poker.transform.localPosition = bee.v3(0, 25)
                end
            end
        end
    end

    QuickByModel:addButtonItem(self.uiName, self.QuickByButton)
end

function P:afterShow()
    if not GuideManager:isInGuide() then
        GuideManager:startSystemGuide(SYS_GUIDES[self._gameType], 0.65)
    end
end

function P:refreshItem(data, item)
    local Root = self:find("Root", item)
    local isLocked = false
    bee.setText(self:find("TextBlind", Root), "" .. _N(data.sb) .. "/" .. _N(data.bb))
    if data.min_byin then
        bee.setText(self:find("TextMMBuyin", Root), "" .. _N(data.min_byin) .. "-" .. _N(data.max_byin))
    else
        bee.setText(self:find("TextMMBuyin", Root), "" .. _N(data.byin))
    end
    if self:find("blinds_tab_recommend", Root) then
        self:find("blinds_tab_recommend", Root):SetActive(self._lastSelectIndex == data.index)
    end
    if self:find("blinds_selected", Root) then
        self:find("blinds_selected", Root):SetActive(self._lastSelectIndex == data.index)
    end
    local Locked = self:find("Locked", Root)
    if Locked then
        if data.level_limit > PlayerModel:getCurLevel() then
            Locked:SetActive(true)
            bee.setText(self:find("Locked/Text", Root), _F("LAB_SYS_UNLOCK_LEVEL", data.level_limit))
            isLocked = true
        else
            Locked:SetActive(false)
        end
    end
    if Locked and not isLocked and (SettingModel:isSysUnlockAnim(data.unlock_id)) then
        Root.transform.localScale = bee.v3one
        if self:find("blinds_tab_recommend", Root) then
            self:find("blinds_tab_recommend", Root):SetActive(false)
        end
        if self:find("blinds_selected", Root) then
            self:find("blinds_selected", Root):SetActive(false)
        end
        Locked:SetActive(true)
        self:find("Text", Locked):SetActive(false)
        self:find("Lock", Locked):SetActive(true)
        self:once(0.5, function()
            self:find("Lock", Locked):SetActive(false)
            local eft = bee.createObj("Prefab/Eff_poker_Ui_Blinds_js")
            eft.transform:SetParent(Locked.transform, false)
            eft.transform.localPosition = self:find("Lock", Locked).transform.localPosition
            self:once(1, function()
                Locked:SetActive(false)
                if self:find("blinds_tab_recommend", Root) then
                    self:find("blinds_tab_recommend", Root):SetActive(self._lastSelectIndex == data.index)
                end
                if self:find("blinds_selected", Root) then
                    self:find("blinds_selected", Root):SetActive(self._lastSelectIndex == data.index)
                end
                if self._lastSelectIndex == data.index then
                    Root.transform.localScale = bee.v3(1.04, 1.04, 1.04)
                else
                    Root.transform.localScale = bee.v3one
                end
            end)
        end)
    else
        if self._lastSelectIndex == data.index then
            Root.transform.localScale = bee.v3(1.04, 1.04, 1.04)
        else
            Root.transform.localScale = bee.v3one
        end
    end
    self:find("Item3", Root):SetActive(false)
    self:find("Item4", Root):SetActive(false)

    if self._gameType ~= GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN then
        if data.min_byin > PlayerModel:getGold() then
            if data.id <= 4 then
                bee.setColor(self:find("TextMMBuyin", Root), bee.colorHex("#dc2c2c"), "Text")
            else
                bee.setColor(self:find("TextMMBuyin", Root), bee.colorHex("#ff4747"), "Text")
            end
        end
    end

    bee.addClick(item, function()
        if data.level_limit and data.level_limit > PlayerModel:getCurLevel() then
            UiManager:showToast(_F("LAB_LEVEL_TEXT_16", data.level_limit))
            return
        end
        if PlayerModel:getGold() < (data.min_byin or data.byin) then
            if data.id <= 1 then
                UiManager:showToast(_T("LAB_GOLD_LACK"))
            else
                UiManager:showToast(_T("LAB_SMALL_THAN_BUYIN"))
            end
            QuickByModel:checkShowView(self._gameType)
        else
            local byinFunc = function()
                if self._gameType == GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN then
                    local params = {
                        boot = data.bb, 
                        game_type = data.gameType, 
                        lobby_coin = GPropId.Gold,
                        byin_chips = data.byin,
                        ip = PlayerModel:getIP(),
                    }
                    Net:sendReq("pb.QuickStartREQ", params)
                    self:hideUI()
                else
                    UiManager:showUI("LobbyByinDialog", {data = data})
                    self._closeAnim = ""
                    self:hideUI()
                end
            end
            
            local key = "OmahaBlinds_byin_recommend_small_" .. PlayerModel:getUid()
            if PlayerModel:getGold() < data.recommend then
                if LocalStore:isDailyTagValid(key, true) then
                    UiManager:showTip({
                        text = _T("LAB_GAME_050"),
                        button = 2,
                        toggle = false,
                        onSure = function(isOn)
                            byinFunc()
                            if isOn then
                                LocalStore:isDailyTagValid(key)
                            end
                        end
                    })
                    return
                end
            end
            byinFunc()
        end
    end)
end

function P:_refreshRewardItem(Room, k, v, game_type)
    local items = {}
    if v.fire_power > 0 then
        table.insert(items, {item_id = GPropId.FirePower, num = v.fire_power})
    end
    if v.win_exp > 0 then
        table.insert(items, {item_id = GPropId.Exp, num = v.win_exp, format = {VipModel:getExpHands()}})
    end
    if v.bond_add > 0 then
        table.insert(items, {item_id = GPropId.Bond, num = v.bond_add, format = {VipModel:getFriendshipHands()}})
    end
    if ThemeModel:isActivityOpen() and not GF.isTrainingGame(game_type) then
        local num = 0
        local d = ThemeModel:getConfData()
        if d then
            for kk, vv in ipairs(d.mod) do
                if vv == self._gameType then
                    if d.mod_add and d.mod_add[kk] and d.mod_add[kk][k] then
                        num = d.mod_add[kk][k]
                    end
                    break
                end
            end
        end
        if num > 0 then
            table.insert(items, {item_id = ThemeModel:getItemId(), num = num})
        end
    end

    local ItemRoot = self:find("Root/Item3", Room)
    if 4 <= #items then
        ItemRoot = self:find("Root/Item4", Room)
    end
    ItemRoot:SetActive(true)
    local Items = {}
    for k, v in ipairs(items) do
        local item01 = self:find("item0" .. k, ItemRoot)
        item01:SetActive(true)
        PropItem:create(item01):setData(v)
        bee.addClick(item01, function()
            UiManager:showUI("CommonItemTip", {data = v, format = v.format, target = item01})
        end)
        table.insert(Items, item01)
    end
    for i = #items + 1, 5 do
        local item01 = self:find("item0" .. i, ItemRoot)
        if item01 then
            item01:SetActive(false)
        end
    end
    
    local aligns = {}
    for _, v in ipairs(Items) do
        if v.activeSelf then
            table.insert(aligns, v)
        end
    end
    if #aligns == 1 then
        aligns[1].transform.localPosition = bee.v3zero
    elseif #aligns == 2 then
        aligns[1].transform.localPosition = bee.v3(-90, 0)
        aligns[2].transform.localPosition = bee.v3(90, 0)
    end
end

function P:refreshRewardItems(game_type)
    if self.reward_list then
        local items = {}
        for k, v in ipairs(self._datas) do
            if v.gameType == game_type then
                table.insert(items, self.CurItems[k])
            end
        end
        for k, v in ipairs(self.reward_list) do
            local Room = items[k]
            if Room then
                self:_refreshRewardItem(Room, k, v, game_type)
            end
        end
    end
end

function P:evt_RoomWinnerRewardsInfoRSP(msg)
    self.reward_list = msg.reward_list
    self:refreshRewardItems(msg.game_type)
end

function P:evt_refreshTopInfo()
    bee.setTextGold(self.TextGold, _N(PlayerModel:getGold()))
    self._curStep = 0
    for i = #self._datas, 1, -1 do
        if PlayerModel:getGold() >= self._datas[i].recommend and (not self._datas[i].level_limit or self._datas[i].level_limit <= PlayerModel:getCurLevel()) then
            self._curStep = i
            break
        end
    end
    self._lastSelectIndex = self._curStep

    for k, v in ipairs(self._datas) do
        local item = self.CurItems[k]
        local Root = self:find("Root", item)
        if self:find("blinds_tab_recommend", Root) then
            self:find("blinds_tab_recommend", Root):SetActive(self._lastSelectIndex == v.index)
        end
        if self:find("blinds_selected", Root) then
            self:find("blinds_selected", Root):SetActive(self._lastSelectIndex == v.index)
        end
        if self._gameType ~= GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN then
            if v.min_byin > PlayerModel:getGold() then
                if v.id <= 4 then
                    bee.setColor(self:find("TextMMBuyin", Root), bee.colorHex("#dc2c2c"), "Text")
                else
                    bee.setColor(self:find("TextMMBuyin", Root), bee.colorHex("#ff4747"), "Text")
                end
            else
                bee.setColor(self:find("TextMMBuyin", Root), bee.colorHex("#262626"), "Text")
            end
        end
        if self._lastSelectIndex == v.index then
            Root.transform.localScale = bee.v3(1.04, 1.04, 1.04)
        else
            Root.transform.localScale = bee.v3one
        end
    end
end

function P:evt_sys_guide_end(guide)
    if guide.id == SYS_GUIDES[self._gameType] then
        if self._horizontalNormalizedPosition then
            bee.Tween.toFloat(0, self._horizontalNormalizedPosition, 0.5, function(value)
                if not bee.isNull(self.node) and not self:isHiding() then
                    self.RoomList:GetComponent("ScrollRect").horizontalNormalizedPosition = value
                end
            end)
        end
    end
end

function P:hideUI()
	P.super.hideUI(self)
	QuickByModel:hideButton(self.QuickByButton)
end

return P