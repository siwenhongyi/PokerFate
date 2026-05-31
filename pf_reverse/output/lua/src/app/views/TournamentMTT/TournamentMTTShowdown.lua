local P = class("TournamentMTTShowdown", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.RightBottom = self:find("RightBottom", self.AnimRoot)
    self.Top = self:find("Top", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)

    self.CharacterImage = self:find("CharacterImage", self.Center)
    self.Player = self:find("Player", self.Bottom)
    self.ImageTitle = self:find("ImageTitle", self.Player)
    self.TextName = self:find("TextName", self.Player)
    self.TextLevel = self:find("Rank/TextLevel", self.Player)

    self.ShareButton = self:find("ShareCont/ShareButton", self.LeftTop)
    self.Sharetips = self:find("ShareCont/Sharetips", self.LeftTop)

    self.TextTitle = self:find("TextTitle", self.Top)

    self.ObserveButton = self:find("ObserveButton", self.Bottom)
    self.CloseButton = self:find("CloseButton", self.RightTop)

    self.Eliminate02 = self:find("Eliminate02", self.Center)
    self.TextRank01 = self:find("TextRank01", self.Eliminate02)
    self.TextRank02 = self:find("TextRank02", self.Eliminate02)

    bee.addClick(self.CloseButton, function()
		Game:playSound("ui_button_confirm")
        bee.enterScene("MainScene", { info = {
            key = "tournament",
            kind = 3,
        }})
    end)
    bee.addClick(self.ObserveButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("tournament-view", 2, GameModel.data.room_info.tour_id)
		Net:sendReq("pb.EnterRoomREQ", {roomid = GameModel.data:getRoomId(), is_observer = true, uid_being_observed = PlayerModel:getUid()})
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

    self._data = self._params and self._params.data
    if not self._data then
        self._data = {
            rank = 1, 
            champion_points = 10, 
            sign_item_list = {{item_num = 30000, item_id = 10100001}}, 
            reward = {{item_id = 20410201, item_num = 1000}, {item_id = 10100001, item_num = 1000}, {item_id = 10100001, item_num = 1000}, {item_id = 10100001, item_num = 1000}}, 
            bond_inc = 10, 
            exp_inc = 10, 
            tour_name = {}, 
            tour_id=16,
            skin_id = 0,
            is_enter_win_round = true,
        }
    end
    self.ObserveButton:SetActive(self._data.rank > 2)
    
    local skin = tpl_character_skin[self._data.skin_id or 0]
    bee.setTextCut(self.TextName, PlayerModel:getName(), 460)
    bee.setText(self.TextLevel, PlayerModel:getCurLevel())
    if PlayerModel:getCurLevel() > 0 then
        bee.setIcon(self:find("Rank/icon_rank_01", self.Player), tpl_level[PlayerModel:getCurLevel()].icon)
    end
    GF.setTitleImage(self.ImageTitle, PlayerModel:getTitle(), true, true)

    for _, v in ipairs(self._data.tour_name) do
        if v.lang == LAN:getLanguage() then
            bee.setText(self.TextTitle, v.text)
            break
        end
    end
    bee.setText(self.TextRank01, _T("LAB_TOURNAMENT_SNG_INFO34") .. _N(self._data.rank))
    bee.setText(self.TextRank02, _T("LAB_TOURNAMENT_SNG_INFO34") .. _N(self._data.rank))

    bee.invoke(self.CharacterImage, "setSkin", skin or CharacterModel:getUsingRole():getSkinData(), false, true)
    bee.invoke(self.CharacterImage, "setSkinRotate")
    Game:playSound("sound_SNG_win")

    local Rewards01 = self:find("Rewards01", self.Eliminate02)
    local Rewards02 = self:find("Rewards02", self.Eliminate02)
    local BgView01 = self:find("BgView", Rewards01)
    local BgView02 = self:find("BgView", Rewards02)
    local Item1 = self:find("Item1", Rewards01)
    Item1:SetActive(false)
    local Item3 = self:find("Item3", Rewards02)
    Item3:SetActive(false)

    local flag01, flag02 = false, false
    local reward = self._data.reward or {}
    if self._data.champion_points > 0 then
        table.insert(reward, {item_id = GPropId.ChampionPoints, item_num = self._data.champion_points})
    end
    if #reward > 3 then
        BgView01 = self:find("ViewItems/Viewport/Content", Rewards01)
    end
    flag01 = #reward > 0
    GF.addItemsToParent(BgView01, Item1, reward, #reward > 3 and {} or nil)

    reward = {}
    if self._data.bond_inc > 0 then
        table.insert(reward, {item_id = GPropId.BondSNG, item_num = self._data.bond_inc, format = {VipModel:getFriendshipTournament()}})
    end
    if self._data.exp_inc > 0 then
        table.insert(reward, {item_id = GPropId.ExpSNG, item_num = self._data.exp_inc, format = {VipModel:getExpTournament()}})
    end
    for _, v in ipairs(reward) do
        if v.item_id == GPropId.BondSNG or v.item_id == GPropId.ExpSNG then
            flag02 = true
            local item = CU.GameObject.Instantiate(Item3, BgView02.transform, false)
            item:SetActive(true)
            PropItem:create(item, {id = v.item_id, num = v.item_num, format = v.format}): bindTips()
        end
    end
    
    Rewards01:SetActive(flag01)
    Rewards02:SetActive(flag02)
    if not flag02 then
        Rewards01.transform.localPosition = bee.v3(Rewards01.transform.localPosition.x, -98, 0)
    end

    self.TextRank01:SetActive(flag01 and flag02)
    self.TextRank02:SetActive(not flag01 or not flag02)
    
    Game:stopMusic()
end

function P:onHide()
    GameModel:setStopLeaveRoom(nil)
    bee.emit("evt_gameBlur", false, self.__cname)
    P.super.onHide(self)
end

return P