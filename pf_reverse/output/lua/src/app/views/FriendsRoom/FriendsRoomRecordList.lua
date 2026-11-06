local P = class("FriendsRoomRecordList", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    
    self.Piyo01List = self:find("Piyo01List", self.Panel)
    self.Piyo02List = self:find("Piyo02List", self.Panel)
    self.Item01 = self:find("Item01", self.Piyo01List)
    self.Item01:SetActive(false)

    self.Empty = self:find("Empty", self.Panel)
    self.Filter = self:find("Filter", self.Panel)

    self.CheckToggle = self:find("CheckToggle", self.Panel)

    bee.addClick(self:find("RefreshButton", self.Panel), function()
        Game:playSound("ui_button_confirm")
        Net:sendReq("pb.GetFriendHisRecordREQ", {})
        bee.logEvent("friendsroom-room-list-refresh")
    end)
    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("Locked/UnlockButton", self.Panel), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("friendsroom-monthlypass-unlock")
        ItemModel:jumpView(101002)
    end)
    
    bee.addValueChanged(self.CheckToggle, function(isOn)
        Game:playSound("ui_button_disabled")
        self:refreshList()
        bee.logEvent("friendsroom-history-filter", isOn and 1 or 0, self._filter_game_types[self._filterIdx])
    end)

    self._filter_game_types = {
        0,
        GAME_GAME_TYPE.FRIEND_HOLDEM_GAME, 
        GAME_GAME_TYPE.FRIEND_OMAHA_GAME, 
        GAME_GAME_TYPE.FRIEND_SNG_GAME, 
    }
    self.Filter = UiFilterBox:create(self.Filter, self:find("FilterArea", self.Filter), self.node)
    self.Filter:setDatas({
        _T("LAB_FRIROOM_034"),
        _T("LAB_POKER_GAME"),
        _T("LAB_OMAHA"),
        _T("LAB_SNG"),
    })
    self.Filter:setSelectFunc(function(idx, data)
        -- self:setCurGameType(self._filter_game_types[idx])
        self._filterIdx = idx
        -- self:setFilterText(self.TextFilter, self._filterIdx)
        self:refreshList()
    end)

    self.ListHistory01 = UiListEx:create(self.Piyo01List)
    self.ListHistory01:setWidth(220)
    self.ListHistory01:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item01)
    end)
    self.ListHistory01:setRefreshFunc(function(data, item)
        self:refreshItem(data, item)
    end)
    self.ListHistory02 = UiListEx:create(self.Piyo02List)
    self.ListHistory02:setWidth(220)
    self.ListHistory02:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item01)
    end)
    self.ListHistory02:setRefreshFunc(function(data, item)
        self:refreshItem(data, item)
    end)
end

function P:onShow()
    self._filterIdx = 1
    -- self:setFilterText(self.TextFilter, self._filterIdx)

    self:refreshLocked()

    self._datas = {}
    self.Empty:SetActive(true)
    self.PiyoList:SetActive(false)
    Net:sendReq("pb.GetFriendHisRecordREQ", {req_type = 0})

    -- local test_data = {
    --     {
    --         setid = "",
    --         creater = {
    --             uid = PlayerModel:getUid(),
    --             name = PlayerModel:getName(),
    --             frame = PlayerModel:getFrame(),
    --         },
    --         game_type = GAME_GAME_TYPE.FRIEND_HOLDEM_GAME,
    --         seat_num = 3,
    --         bb = 100,
    --         min_byin = 1000,
    --         max_byin = 2000,
    --         end_time = os.time(),
    --         player_num = 3,
    --         roomid = 0,
    --         is_eliminate = false,
    --         rank = 1,
    --         profit = 1000,
    --     },{
    --         setid = "",
    --         creater = {
    --             uid = PlayerModel:getUid(),
    --             name = PlayerModel:getName(),
    --             frame = PlayerModel:getFrame(),
    --         },
    --         game_type = GAME_GAME_TYPE.FRIEND_SNG_GAME,
    --         seat_num = 3,
    --         bb = 100,
    --         min_byin = 1000,
    --         max_byin = 2000,
    --         end_time = os.time(),
    --         player_num = 3,
    --         roomid = 0,
    --         is_eliminate = false,
    --         rank = 1,
    --         profit = 1000,
    --     },
    -- }
    -- self._datas = test_data
    -- self:refreshList()
end

function P:refreshLocked()
    local flag = ShopModel:isMonthlyCard()
    self:find("Unlock", self.Panel):SetActive(flag)
    self:find("Locked", self.Panel):SetActive(not flag)

    self.Piyo01List:SetActive(flag)
    self.Piyo02List:SetActive(not flag)

    self.PiyoList = flag and self.Piyo01List or self.Piyo02List
    self.ListHistory = flag and self.ListHistory01 or self.ListHistory02
end

function P:refreshList()
    local datas = {}
    local onlyEnd = bee.isCheck(self.CheckToggle)
    for _, v in ipairs(self._datas) do
        if (not onlyEnd or v.end_time > 0) and (1 == self._filterIdx or v.game_type == self._filter_game_types[self._filterIdx]) then
            table.insert(datas, v)
        end
    end
    self.Empty:SetActive(0 == #datas)
    self.PiyoList:SetActive(#datas > 0)
    self.ListHistory:setDatas(datas)
end

function P:refreshItem(data, item)
    self:find("TextDissolve", item):SetActive(data.offline_room_over)
    bee.setTextCut(self:find("TextName", item), data.creater.name, 217)
    bee.setIcon(self:find("Avatar/Mask/ImageIcon", item), PlayerModel:getAvatarIcon(data.creater.avatar))
    GF.setFrameImage(self:find("Avatar/ImageFrame", item), data.creater.frame)

    if GF.isFriendSNG(data.game_type) then
        bee.setText(self:find("TextSngName", item), _F("LAB_FRIROOM_059", data.seat_num))
        self:find("Blind", item):SetActive(false)
        self:find("Buyin", item):SetActive(false)

        bee.setText(self:find("TextWin", item), "#" .. data.rank)
        bee.setText(self:find("TextLose", item), "")
    else
        bee.setText(self:find("TextSngName", item), "")
        self:find("Blind", item):SetActive(true)
        self:find("Buyin", item):SetActive(true)
        bee.setText(self:find("Blind/TextBlind", item), _N(data.bb / 2) .. "/" .. _N(data.bb))
        bee.setText(self:find("Buyin/TextByin", item), _N(data.min_byin) .. "-" .. _N(data.max_byin))

        if data.profit > 0 then
            bee.setText(self:find("TextWin", item), "+" .. data.profit)
            bee.setText(self:find("TextLose", item), "")
        else
            bee.setText(self:find("TextWin", item), "")
            bee.setText(self:find("TextLose", item), data.profit)
        end
    end

    local gameName = GF.getGameTypeName(data.game_type)
    bee.setText(self:find("TextGame", item), gameName)

    local s = string.format("%d/%d", data.player_num, data.seat_num)
    bee.setText(self:find("TextNum1", item), s)

    local JoinButton = self:find("Joinbutton", item)
    local WatchButton = self:find("WatchButton", item)
    local Returnbutton = self:find("Returnbutton", item)
    local CheckButton = self:find("CheckButton", item)

    JoinButton:SetActive(false)
    WatchButton:SetActive(false)
    Returnbutton:SetActive(false)
    CheckButton:SetActive(false)

    if data.end_time == 0 then
        if GF.isFriendSNG(data.game_type) then
            if data.is_eliminate then
                WatchButton:SetActive(true)
                bee.addClick(WatchButton, function()
                    Game:playSound("ui_button_confirm")
                    Net:sendReq("pb.JoinFriendRoomREQ", {
                        roomid = tonumber(data.roomid),
                        is_observer = true,
                    })
                    bee.logEvent("friendsroom-history-detail", 4)
                end, true)
            else
                Returnbutton:SetActive(true)
                bee.addClick(Returnbutton, function()
                    Game:playSound("ui_button_confirm")
                    Net:sendReq("pb.JoinFriendRoomREQ", {
                        roomid = tonumber(data.roomid),
                    })
                    bee.logEvent("friendsroom-history-detail", 2)
                end, true)
            end
        else
            JoinButton:SetActive(true)
            bee.addClick(JoinButton, function()
                Game:playSound("ui_button_confirm")
                Net:sendReq("pb.JoinFriendRoomREQ", {
                    roomid = tonumber(data.roomid),
                })
                bee.logEvent("friendsroom-history-detail", 1)
            end, true)
        end
        bee.setText(self:find("TextTime", item), "")
        self:find("TextNum1", item):SetActive(true)
    else
        bee.setText(self:find("TextTime", item), _T("LAB_FRIROOM_064") .. TimeHelp:getDateTimeStr(data.end_time))
        self:find("TextNum1", item):SetActive(false)
        CheckButton:SetActive(true)
        bee.addClick(CheckButton, function()
            Game:playSound("ui_button_confirm")
            UiManager:showUI("FriendsRoomScoreBoard", {data = data})
            bee.logEvent("friendsroom-history-detail", 3)
        end, true)
    end
end

function P:evt_GetFriendHisRecordRSP(msg)
    self._datas = msg.records
    table.sort(self._datas, function(a, b)
        if a.end_time == b.end_time then
            return false
        end
        if a.end_time == 0 then
            return true
        elseif b.end_time == 0 then
            return false
        end
        return a.end_time > b.end_time
    end)
    self:refreshList()
end

function P:evt_updateMonthlyCard()
	self:refreshLocked()
    self:refreshList()
end

return P