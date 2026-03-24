local P = class("TournamentSNGShowdown", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.RightBottom = self:find("RightBottom", self.AnimRoot)
    self.Top = self:find("Top", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)

    self.CharacterImage = self:find("CharacterImage", self.Center)
    self.Player = self:find("Player", self.Center)
    self.ImageTitle = self:find("ImageTitle", self.Player)
    self.TextName = self:find("TextName", self.Player)
    self.TextLevel = self:find("Rank/TextLevel", self.Player)

    self.ShareButton = self:find("ShareCont/ShareButton", self.LeftTop)
    self.Sharetips = self:find("ShareCont/Sharetips", self.LeftTop)

    self.TextTitle = self:find("TextTitle", self.Top)

    self.BuyIn = self:find("BuyIn", self.Bottom)
    self.NextButton = self:find("NextButton", self.Bottom)
    self.CloseButton = self:find("CloseButton", self.Bottom)

    self.Eliminated = self:find("Eliminated", self.Center)
    self.WIN = self:find("WIN", self.Center)

    bee.addClick(self.CloseButton, function()
		Game:playSound("ui_button_confirm")
        bee.enterScene("MainScene", { info = {
            key = "tournament",
            kind = 2,
        }})
    end)
    bee.addClick(self.NextButton, function()
		Game:playSound("ui_button_confirm")
        
        if self.signItem and self.signItem.item_num > ItemModel:getItemNumById(self.signItem.item_id) then
            UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[self.signItem.item_id].name)))
            return
        end
        if not bee.checkCd("SngSignREQ", 2) then
            return
        end
        TournamentModel:reqSngSign(self._data, self.signItem and self.signItem.item_id or 0, function()
        end)
    end)
    bee.addClick(self.ShareButton, function()
        Game:playSound("ui_button_confirm")
        self.CloseButton:SetActive(false)
        self.NextButton:SetActive(false)
        self.BuyIn:SetActive(false)
        self.ShareButton:SetActive(false)
        self.Sharetips:SetActive(false)
        UiManager:showUI("ShareMain", {id = 6})
        self:once(1, function()
            self.CloseButton:SetActive(true)
            self.NextButton:SetActive(true)
            self.BuyIn:SetActive(true)
            self.ShareButton:SetActive(true)
        end)
    end)

    GameModel:setStopLeaveRoom(true)
end

function P:onShow()
    GameModel:setStopLeaveRoom(true)
    Game:stopRoleSound()
    bee.emit("evt_gameBlur", true, self.__cname)

    self._data = self._params and self._params.data or {rank = 1, champion_points = 10, sign_item_list = {{item_num = 30000, item_id = 10100001}}, reward = {{item_id = 10100001, item_num = 1000}}, bond_inc = 10, exp_inc = 10, tour_name = {}, tour_id=16}

    local skin = tpl_character_skin[self._data.skin_id or 0]
    bee.setTextCut(self.TextName, PlayerModel:getName(), 460)
    bee.setText(self.TextLevel, PlayerModel:getCurLevel())
    if PlayerModel:getCurLevel() > 0 then
        bee.setIcon(self:find("Rank/icon_rank_01", self.Player), tpl_level[PlayerModel:getCurLevel()].icon)
    end
    GF.setTitleImage(self.ImageTitle, PlayerModel:getTitle(), true, true)

    -- self.Eliminated:SetActive(self._data.rank ~= 1)
    -- self.WIN:SetActive(self._data.rank == 1)
    for _, v in ipairs(self._data.tour_name) do
        if v.lang == LAN:getLanguage() then
            bee.setText(self.TextTitle, v.text)
            break
        end
    end

    self.signItem, self.itemData = nil, nil
    bee.removeAllClick(self:find("tournament_lobby_frame_01", self.BuyIn))
    if #self._data.sign_item_list > 0 then
        for k, v in ipairs(self._data.sign_item_list) do
            self.itemData = ItemModel:getItem(v.item_id, true)
            if self.itemData.num >= v.item_num or k == #self._data.sign_item_list then
                self:find("tournament_lobby_frame_01/icon_10100001", self.BuyIn):SetActive(true)
                bee.setIcon(self:find("tournament_lobby_frame_01/icon_10100001", self.BuyIn), tpl_props[v.item_id].icon)
                -- bee.setText(self:find("TextByin", self.BuyIn), _N(v.item_num))
                self.signItem = v
                bee.addClick(self:find("tournament_lobby_frame_01", self.BuyIn), function()
                    UiManager:showUI("CommonItemTip", {data = self.itemData, target = self:find("tournament_lobby_frame_01", self.BuyIn)})
                end, true)
                break
            end
        end
    else
        self:find("tournament_lobby_frame_01/icon_10100001", self.BuyIn):SetActive(false)
        -- bee.setText(self:find("TextByin", self.BuyIn), _T("LAB_SHOP_COMMON_21"))
    end
    TournamentModel:setByinText(self:find("tournament_lobby_frame_01/TextByin", self.BuyIn), self.signItem, true)

    if 1 == self._data.rank and self.ShareButton then
        bee.invoke(self.CharacterImage, "setSkin", skin or CharacterModel:getUsingRole():getSkinData(), false)
        Game:playSound("sound_SNG_win")
        self.ShareButton:SetActive(true)
        self.Sharetips:SetActive(not bee.isPc and not ShareModel:getPageIsShared(6))

        local Rewards01 = self:find("Rewards01", self.Bottom)
        local Rewards02 = self:find("Rewards02", self.Bottom)
        local BgView = self:find("BgView", Rewards02)
        local Item3 = self:find("Item3", Rewards02)
        Item3:SetActive(false)

        bee.setText(self:find("Item2/CountText", Rewards01), _N(self._data.champion_points))
        bee.addClick(self:find("Item2", Rewards01), function()
            UiManager:showUI("CommonItemTip", {data = {id = GPropId.ChampionPoints}, target = self:find("Item2/Icon", Rewards01)})
        end, true)
        local flag = false
        for _, v in ipairs(self._data.reward) do
            if v.item_id == GPropId.Gold then
                bee.setText(self:find("Item1/CountText", Rewards01), _N(v.item_num))
                bee.addClick(self:find("Item1", Rewards01), function()
                    UiManager:showUI("CommonItemTip", {data = {id = GPropId.Gold}, target = self:find("Item1/Icon", Rewards01)})
                end, true)
            else
                flag = true
                local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
                item:SetActive(true)
                PropItem:create(item, {id = v.item_id, num = v.item_num}): bindTips()
                if tpl_props[v.item_id].type == GPropKind.Title then
                    local Icon = self:find("Icon", item)
                    Icon.transform.sizeDelta = bee.v2(260, 45)
                end
            end
        end
        if self._data.bond_inc > 0 then
            flag = true
            local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
            item:SetActive(true)
            PropItem:create(item, {id = GPropId.BondSNG, num = self._data.bond_inc, format = {VipModel:getFriendshipTournament()}}): bindTips()
        end
        if self._data.exp_inc > 0 then
            flag = true
            local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
            item:SetActive(true)
            PropItem:create(item, {id = GPropId.ExpSNG, num = self._data.exp_inc, format = {VipModel:getExpTournament()}}): bindTips()
        end
        Rewards02:SetActive(flag)
        if not flag then
            Rewards01.transform.localPosition = bee.v3(0, 100, 0)
        end
    else
        bee.invoke(self.CharacterImage, "setSkin", skin or CharacterModel:getUsingRole():getSkinData(), false)
        bee.invoke(self.CharacterImage, "playAnim", "idle", "skin2", "standby")
        Game:playSound("sound_SNG_lose")
        -- self.ShareButton:SetActive(false)
        -- self.Sharetips:SetActive(false)
        -- self:find("Rewards01", self.Bottom):SetActive(false)
        -- self:find("Rewards02", self.Bottom):SetActive(false)

        local Rewards01 = self:find("Reward01", self.Eliminated)
        local Rewards02 = self:find("Reward02", self.Eliminated)
        local BgView = self:find("BgView", Rewards02)
        local Item3 = self:find("Item3", Rewards02)
        Item3:SetActive(false)

        bee.setText(self:find("Item2/CountText", Rewards01), _N(self._data.champion_points))
        local flag = false
        for _, v in ipairs(self._data.reward) do
            flag = true
            local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
            item:SetActive(true)
            PropItem:create(item, {id = v.item_id, num = v.item_num}): bindTips()
        end
        if self._data.bond_inc > 0 then
            flag = true
            local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
            item:SetActive(true)
            PropItem:create(item, {id = GPropId.BondSNG, num = self._data.bond_inc, format = {VipModel:getFriendshipTournament()}}): bindTips()
        end
        if self._data.exp_inc > 0 then
            flag = true
            local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
            item:SetActive(true)
            PropItem:create(item, {id = GPropId.ExpSNG, num = self._data.exp_inc, format = {VipModel:getExpTournament()}}): bindTips()
        end
        Rewards01:SetActive(not flag)
        Rewards02:SetActive(flag)
        if flag then
            bee.setText(self:find("TextRank", Rewards02), _T("LAB_TOURNAMENT_SNG_INFO34") .. _N(self._data.rank))
        else
            bee.setText(self:find("TextRank", Rewards01), _T("LAB_TOURNAMENT_SNG_INFO34") .. _N(self._data.rank))
        end
    end
    Game:stopMusic()
end

function P:onHide()
    GameModel:setStopLeaveRoom(nil)
    bee.emit("evt_gameBlur", false, self.__cname)
    P.super.onHide(self)
end

