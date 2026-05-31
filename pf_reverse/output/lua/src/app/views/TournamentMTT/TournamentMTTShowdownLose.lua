local P = class("TournamentMTTShowdownLose", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.Top = self:find("Top", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)

    self.TextTitle = self:find("TextTitle", self.Top)

    self.ObserveButton = self:find("ObserveButton", self.Bottom)
    self.CloseButton = self:find("CloseButton", self.RightTop)

    self.Eliminate01 = self:find("Eliminate01", self.Center)
    self.TextRank = self:find("TextRank", self.Eliminate01)

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
            reward = {{item_id = 10100001, item_num = 1000}}, 
            bond_inc = 10, 
            exp_inc = 10, 
            tour_name = {}, 
            tour_id=16,
            skin_id = 0,
            is_enter_win_round = false,
        }
    end

    for _, v in ipairs(self._data.tour_name) do
        if v.lang == LAN:getLanguage() then
            bee.setText(self.TextTitle, v.text)
            break
        end
    end
    bee.setText(self.TextRank, _F("LAB_TOURNAMENT_MTT_INFO37", _N(self._data.rank)))

    Game:playSound("sound_SNG_lose")

    local Rewards02 = self:find("Rewards02", self.Eliminate01)
    local BgView = self:find("BgView", Rewards02)
    local Item3 = self:find("Item3", Rewards02)
    Item3:SetActive(false)

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
    Rewards02:SetActive(flag)
        
    Game:stopMusic()
end

function P:onHide()
    GameModel:setStopLeaveRoom(nil)
    bee.emit("evt_gameBlur", false, self.__cname)
    P.super.onHide(self)
end

return P