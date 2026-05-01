local P = class("InformationMainNew", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.Panel = self:find("Panel", self.Center)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)

    self.CharacterImage = self:find("CharacterImage", self.Center)

    self.Tips = self:find("Tips", self.Center)
    self.Info1 = self:find("Info1", self.Panel)
    self.Info2 = self:find("Info2", self.Panel)
    self.Info3 = self:find("Info3", self.Panel)

    self.Edit_01_Button = self:find("Edit_01_Button", self.Info1)
    self.Edit_02_Button = self:find("Edit_02_Button", self.Info1)
    self.CopyButton = self:find("Uid", self.Info1)
    self.Avatar = self:find("Avatar", self.Info1)
    self.TextName = self:find("Name/TextName", self.Info1)
    self.TextUID = self:find("Uid/TextUID", self.Info1)
    self.ImageTitle = self:find("ImageTitle", self.Info1)
    self.TextLevel = self:find("Rank/TextLevel", self.Info1)
    self.ImageFrame = self:find("ImageFrame", self.Info1)
    self.CertificationIcon = self:find("Certification/CertificationIcon", self.Info1)
    self.CertificationText = self:find("Certification/CertificationText", self.Info1)

    self.Edit_03_Button = self:find("Comment/EditButton", self.Info2)
    self.TextDec = self:find("Comment/TextDec", self.Info2)

    self.Edit_04_Button = self:find("Character/Edit_04_Button", self.Info2)
    self.TextEmpty = self:find("Character/TextEmpty", self.Info2)
    self.BgAvatars = {
        self:find("Character/BgAvatar1", self.Info2),
        self:find("Character/BgAvatar2", self.Info2),
        self:find("Character/BgAvatar3", self.Info2),
        self:find("Character/BgAvatar4", self.Info2),
    }
    self.Item1 = self:find("Character/Item1", self.Info2)
    self.Item1:SetActive(false)

    self.ZoomButton = self:find("ZoomButton", self.Center)
    self.AddFriendButton = self:find("AddFriendButton", self.RightTop)
    self.ReportButton = self:find("ReportButton", self.RightTop)
    self.ChatButton = self:find("ChatButton", self.RightTop)
    self.ShareCont = self:find("ShareCont", self.RightTop)
    self.ShareButton = self:find("ShareButton", self.ShareCont)
    self.ShareCont:SetActive(false)

    self.TextCollects = {
        self:find("Collection/TextNum1", self.Info2),
        self:find("Collection/TextNum2", self.Info2),
        self:find("Collection/TextNum3", self.Info2),
        self:find("Collection/TextNum4", self.Info2),
    }

    self.TextAchievements = {
        self:find("Achievement/01/TextNum", self.Info2),
        self:find("Achievement/02/TextNum", self.Info2),
        self:find("Achievement/03/TextNum", self.Info2),

    }

    self.GameFilter = self:find("GameFilter", self.Info3)
    local Content = self:find("RecordList/Viewport/Content", self.Info3)
    self.Statistics = self:find("Statistics", Content)
    self.MaxCardtype = self:find("MaxCardtype", Content)
    self.MaxWinCardtype = self:find("MaxWinCardtype", Content)
    self.Trend = self:find("Trend", Content)

    self.TextGameType = self:find("Info/TextGameType", self.Statistics)
    self.ItemGameNum = self:find("Info/ItemGameNum", self.Statistics)
    self.TextGameNum = self:find("TextGameNum", self.ItemGameNum)
    self.InfoView = self:find("Info/InfoView", self.Statistics)
    self.InfoViewPos = self.InfoView.transform.localPosition
    self.InfoItem1 = self:find("Info/Item1", self.Statistics)
    self.InfoItem1:SetActive(false)
    self.InfoLock = self:find("Lock", self.Statistics)
    self.InfoUnlock = self:find("Unlock", self.Statistics)
    self.InfoUnlock:SetActive(false)

    self.Rates = {
        self:find("Rate1", self.Statistics),
        self:find("Rate2", self.Statistics),
        self:find("Rate3", self.Statistics),
        self:find("Unlock/Rate4", self.Statistics),
        self:find("Unlock/Rate5", self.Statistics),
        self:find("Unlock/Rate6", self.Statistics),
    }
    
    self.TrendView = self:find("View", self.Trend)
    self.TrendPoint = self:find("Point", self.Trend)
    self.TrendLine = self:find("Line", self.Trend)
    self.TrendPoint:SetActive(false)
    self.TrendLine:SetActive(false)

    self.Tabs = {
        self:find("Tab/Tab1Toggle", self.Panel),
        self:find("Tab/Tab2Toggle", self.Panel),
    }

    bee.onCheck(self.Tabs[1], function(isOn)
        if isOn then
            self.Info2:SetActive(true)
            self.Info3:SetActive(false)
		    Game:playSound("ui_tab_switch_1")
        end
    end)
    bee.onCheck(self.Tabs[2], function(isOn)
        if isOn then
            self.Info2:SetActive(false)
            self.Info3:SetActive(true)
		    Game:playSound("ui_tab_switch_1")
        end
    end)

    bee.addClick(self.CopyButton, function()
        CS.SdkHelper.copyText("" .. (self._uid or PlayerModel:getUid()))
        UiManager:showToast(_T("LAB_COPY_SUC"))
    	bee.logEvent("profile-copy-uid")
    end)
    bee.addClick(self:find("Rank", self.Info1), function()
        if self._uid == PlayerModel:getUid() and not self._hideOperate then
            Game:playSound("ui_button_confirm")
            UiManager:showUI("Level")
            bee.logEvent("level-profile")
        end
    end)

    bee.addClick(self.Edit_01_Button, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("InformationRename")
    	bee.logEvent("profile-nickname")
    end)
    bee.addClick(self.Edit_02_Button, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("InformationAvatar", {index = 3})
    	bee.logEvent("profile-title")
    end)
    bee.addClick(self.Edit_03_Button, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("InformationManifesto")
    	bee.logEvent("profile-bio")
    end)
    bee.addClick(self.Edit_04_Button, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("InformationAvatarDetail")
    	bee.logEvent("profile-favorite-char")
    end)
    bee.addClick(self.Avatar, function()
        if self._uid == PlayerModel:getUid() and not self._hideOperate then
            Game:playSound("ui_button_confirm")
            UiManager:showUI("InformationAvatar", {index = 1})
    	    bee.logEvent("profile-avatar")
        end
    end)

    bee.addClick(self.ShareButton, function()
        UiManager:showUI("ShareMain", {id = 1})
    end)

    local InfoButton = self:find("title/Text/common_button_info_05", self.Info5)
    bee.addClick(InfoButton, function()
        Game:playSound("ui_button_confirm")
        self.Tips:SetActive(not self.Tips.activeSelf)
        local pos = self.Tips.transform.position
        pos.x = InfoButton.transform.position.x
        self.Tips.transform.position = pos
    end)

    bee.addClick2(self:find("Image", self.Tips), function()
        Game:playSound("ui_button_confirm")
        self.Tips:SetActive(false)
    end)

    bee.addClick(self.ZoomButton, function()
        Game:playSound("ui_button_confirm")
        if self._uid == PlayerModel:getUid() then
            UiManager:showUI("CharacterMain", {role_id = CharacterModel:getUsingRole():getUsingSkin()})
        else
            UiManager:showUI("CharacterMain", {role_id = self.other_skin_id})
        end
    end)

    bee.addClick(self.ReportButton, function()
        Game:playSound("ui_button_confirm")
    end)
    bee.addClick(self.ChatButton, function()
        Game:playSound("ui_button_confirm")
        Net:sendReq("pb.SetBlockChatREQ", {
            the_uid = self._uid,
            is_block = not PlayerModel:isBlockChat(self._uid),
        })
        local flag = not PlayerModel:isBlockChat(self._uid)
        self:find("Off", self.ChatButton):SetActive(flag)
        self:find("On", self.ChatButton):SetActive(not flag)
        if flag and self._params and self._params.from == "table" then
    	    bee.logEvent("ingame-profile-block", GameModel.data:getGameType(), GameModel.data:getRoomId(), self._uid)
        end
    end)
    bee.addClick(self.AddFriendButton, function()
        Game:playSound("ui_button_confirm")
        FriendModel:addFriend(self._uid)
        if self._params and self._params.from == "table" then
    	    bee.logEvent("ingame-profile-add-friend", GameModel.data:getGameType(), GameModel.data:getRoomId(), self._uid)
        end
    end)

    self.BackButton = self:find("BackButton", self.LeftTop)
    bee.addClick(self.BackButton, function()
        self:hideUI()
    end)

    bee.addClick(self:find("common_button_info_07", self.TextGameType), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonRules", {text = _T("LAB_INFO_064"), title = _T("LAB_INFO_068")})
    end)

    bee.addClick(self:find("UnlockButton", self.InfoLock), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("ShopMonthlyCardPurchase")
    end)

    bee.addClick(self:find("level_button_info", self.InfoLock), function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("ShopMonthlyCardRules")
    end)

    self._sng_count_list = {10, 20, 50}
    self._sng_count_index = 1
    self._sng_count = self._sng_count_list[self._sng_count_index]
    bee.addClick(self:find("Session/common_slider_02_button_plus", self.Trend), function()
        Game:playSound("ui_button_confirm")
        self._sng_count_index = self._sng_count_index + 1
        if self._sng_count_index > #self._sng_count_list then
            self._sng_count_index = #self._sng_count_list
        end
        self._sng_count = self._sng_count_list[self._sng_count_index]
        self:refreshTrend()
    end)
    bee.addClick(self:find("Session/common_slider_02_button_minus", self.Trend), function()
        Game:playSound("ui_button_confirm")
        self._sng_count_index = self._sng_count_index - 1
        if self._sng_count_index < 1 then
            self._sng_count_index = 1
        end
        self._sng_count = self._sng_count_list[self._sng_count_index]
        self:refreshTrend()
    end)

    for _, v in ipairs(self.BgAvatars) do
        bee.addClick(v, function()
            if self._uid == PlayerModel:getUid() and not self._hideOperate then
                Game:playSound("ui_button_confirm")
                UiManager:showUI("InformationAvatarDetail")
            else
                -- item:GetComponent("ButtonZoom").enabled = false
            end
        end)
    end

    if self._uid ~= PlayerModel:getUid() and bee.isInGame() then
        -- 牌局内查看玩家信息
        TaskModel:reportTask(TaskType.CheckView, TaskTargetId.InfoInGame)
    end

    self._filter_game_types = {GAME_GAME_TYPE.LOBBY_HOLDEM_GAME, GAME_GAME_TYPE.LOBBY_OMAHA_GAME, GAME_GAME_TYPE.SNG_HOLDEM_GAME, GAME_GAME_TYPE.FRIEND_HOLDEM_GAME}
    self.Filter = UiFilterBox:create(self.GameFilter, self:find("MusicFilteItem", self.GameFilter), self.node)
    self.Filter:setDatas({
        _T("LAB_POKER_GAME"),
        _T("LAB_OMAHA"),
        _T("LAB_SNG"),
        _T("LAB_FRIROOM_001"),
    })
    self.Filter:setSelectFunc(function(idx, data)
        self:reqGameData(self._filter_game_types[idx])
    end)
end

function P:onShow()
    self.Filter:setDisabled(true)
    self.transform.localPosition = bee.v3zero
    self._uid = self._params and self._params.uid or PlayerModel:getUid()
    if self._uid ~= PlayerModel:getUid() then
        -- 任务进度-查看其他玩家个人信息
        TaskModel:reportTask(TaskType.CheckView, TaskTargetId.Info)
    end

    self._fromTable = self._params and self._params.from == "table"
    self._hideOperate = (self._params and self._params.from == "Ranking") or self._fromTable
    bee.setText(self.TextUID, "UID:" .. self._uid)
    self.CopyButton:SetActive(self._uid == PlayerModel:getUid())
    if self._uid == PlayerModel:getUid() then
        bee.setText(self.TextName, PlayerModel:getName())
        bee.setText(self.TextLevel, PlayerModel:getCurLevel())
        bee.setIcon(self:find("Rank/icon_rank_01", self.Info1), tpl_level[PlayerModel:getCurLevel()].icon)
        bee.setIcon(self:find("Mask/ImageIcon", self.Avatar), PlayerModel:getAvatarIcon())
        bee.invoke(self.CharacterImage, "setSkinImage", CharacterModel:getUsingRole():getSkinData())
        self:evt_ChangeTitleRSP()
        self:evt_ChangeFrameRSP()
        bee.setText(self.TextDec, PlayerModel:getDeclaration())

        PlayerModel:sortFavoriteRoles()
        self:setFavoriteSkins(PlayerModel:getFavoriteRoles())
        self:refreshAchievement()

        for _, v in ipairs(self.TextCollects) do
            bee.setText(v, 0)
        end
        bee.setText(self.TextCollects[1], CharacterModel:getRoleTotalNum())
        bee.setText(self.TextCollects[2], CharacterModel:getSkinTotalNum())
        bee.setText(self.TextCollects[3], ItemModel:getItemDecorationNum())
        bee.setText(self.TextCollects[4], ItemModel:getItemTotalNumByKind(GPropKind.Title))

        self:setShareCont()

        bee.removeAllClick(self.CertificationIcon)
        if PlayerModel:getAuthCertUrl() and PlayerModel:getAuthCertUrl() ~= "" then
            bee.setText(self.CertificationText, _T("LAB_SEVEN_DAY_TASKS_DEC_32"))
            bee.addClick(self.CertificationIcon, function()
                Game:playSound("ui_button_confirm")
                local info = {
                    name = PlayerModel:getName(),
                    uid = self._uid,
                    register_time = PlayerModel:getRegisterTime(),
                    auth_cert_time = PlayerModel:getAuthTime(),
                    auth_cert_url = PlayerModel:getAuthCertUrl(),
                }
                UiManager:showUI("SevenDayTaskCertification", {info = info, isFromTable = self._fromTable})
                
	            bee.logEvent("7daytask-profile", 1)
            end)
        else
            bee.setGrey(self.CertificationIcon, true)
            bee.setText(self.CertificationText, _T("LAB_SEVEN_DAY_TASKS_DEC_31"))
            if not self._fromTable then
                bee.addClick(self.CertificationIcon, function()
                    Game:playSound("ui_button_confirm")
                    UiManager:showUI("SevenDayTaskTips")
		            bee.logEvent("7daytask-profile", 1)
                end)
            else
                self.CertificationIcon:GetComponent("ButtonZoom").enabled = false
            end
        end

        self.AddFriendButton:SetActive(false)
        self.ReportButton:SetActive(false)
        self.ChatButton:SetActive(false)
        if not self._hideOperate then
            self.ShareCont:SetActive(true)
        end
        self.Edit_01_Button:SetActive(not self._hideOperate)
        if self.Edit_02_Button then
            self.Edit_02_Button:SetActive(not self._hideOperate)
        end
        self.Edit_03_Button:SetActive(not self._hideOperate)
        self.Edit_04_Button:SetActive(not self._hideOperate)
        self.ZoomButton:SetActive(not self._hideOperate)
    else
        bee.setText(self.TextName, "")
        self.ImageFrame:SetActive(false)
        self.ImageTitle:SetActive(false)

        self.AddFriendButton:SetActive(true)
        self.ReportButton:SetActive(true)
        self.ChatButton:SetActive(true)
        self.ShareCont:SetActive(false)
        self.Edit_01_Button:SetActive(false)
        if self.Edit_02_Button then
            self.Edit_02_Button:SetActive(false)
        end
        self.Edit_03_Button:SetActive(false)
        self.Edit_04_Button:SetActive(false)
        self.ZoomButton:SetActive(false)
        self.AddFriendButton:SetActive(FriendModel:getFriendInfo(self._uid) == nil)
        self.ChatButton:SetActive(FriendModel:getBlockedInfo(self._uid) == nil)
        if self.ChatButton.activeSelf then
            local flag = PlayerModel:isBlockChat(self._uid)
            self:find("Off", self.ChatButton):SetActive(flag)
            self:find("On", self.ChatButton):SetActive(not flag)
        end
        self.CharacterImage:SetActive(false)
        for i = 1, 4 do
            self.BgAvatars[i]:SetActive(false)
        end

        Net:sendReq("pb.GetOtherDetailInfoREQ", {
            the_uid = self._uid
        })
    end
    -- if self._hideOperate or self._uid ~= PlayerModel:getUid() then
    --     bee.setBtEnable(self.CertificationIcon, false)
    --     self.CertificationIcon:GetComponent("ButtonZoom").enabled = false
    -- end

    if bee.isInTest then
        self.ReportButton:SetActive(false)
    end

    if self._params.from == "lobby" then
        self:infoGuide()
    end

    self._data = {
        game_type = self._filter_game_types[1], -- 游戏类型
        fire_power= 0,  -- 王座积分
        champion_points= 0,  -- 冠军积分
        play_times= 0, -- 已玩手牌数
        win_play_times= 0,  -- 获胜手牌数
        round = 0, -- 总场次
        win_round= 0, -- 获胜场次
        tour_round = 1,
        tour_win_round = 0,
        tour_max_profit = 0,
        tour_profit = 0,
        max_profit= 0, -- 单次最高奖池
        profit= 0, -- 累计获胜奖池
        pool_entry_rate= 0, -- 入池率
        add_before_flipping_rate= 0, -- 翻牌前加注率
        three_bet_rate= 0, -- 3bet率
        show_hand_rate= 0, -- 摊牌率
        active_rate= 0, -- 激进系数
        c_bete_rate= 0, -- c-bet率
        best_cards = nil, -- 最佳牌型
        max_profit_cards= nil -- 获胜最大奖池牌型
    }
    
    self:refreshGameData(self._data)

    local flag = true
    if GameModel.data then
        for k, v in ipairs(self._filter_game_types) do
            if GameModel.data:getGameType() == v then
                self.Filter:setSelectIdx(k)
                flag = false
                break
            end
        end
        
        bee.setCheck(self.Tabs[2], true)
        self.Info2:SetActive(false)
        self.Info3:SetActive(true)
    else
        self:reqGameData(self._filter_game_types[self.Filter:getSelectIdx()])
    end
end

function P:afterShow()
    self.Filter:setDisabled(false)
end

function P:reqGameData(game_type)
    self._game_type = game_type
    Net:post("/player/gameData", {game_type = game_type, player_uid = self._uid, lang = LAN:getLanguage()}, function(data)
        if not bee.isNull(self.node) and 0 == data.code and data.data.game_type == self._game_type then
            self:refreshGameData(data.data)
        end
    end)
end

function P:refreshGameData(data)
    self.InfoUnlock:SetActive(ShopModel:isMonthlyCard())
    self.InfoLock:SetActive(not ShopModel:isMonthlyCard())

    self:removeAllChildren(self.InfoView)
    -- bee.setText(self.TextGameType, GF.getGameTypeName(data.game_type, true))
    if data.game_type == GAME_GAME_TYPE.LOBBY_HOLDEM_GAME or data.game_type == GAME_GAME_TYPE.LOBBY_OMAHA_GAME or data.game_type == GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN then
        self:_addInfoItem(_T("LAB_INFO_046"), data.play_times)
        self:_addInfoItem(_T("LAB_INFO_047"), data.win_play_times)
        self:_addInfoItem(_T("LAB_INFO_048"), _N(data.profit))
        self.ItemGameNum:SetActive(true)
        self:find("information_icon_title_01", self.ItemGameNum):SetActive(true)
        self:find("information_icon_title_02", self.ItemGameNum):SetActive(false)
        self.InfoView.transform.localPosition = self.InfoViewPos

        bee.setText(self.TextGameNum, data.fire_power)
        self.MaxWinCardtype:SetActive(true)
        self:refreshCardType(data.max_profit_cards, self.MaxWinCardtype)
        self.Trend:SetActive(false)
    elseif GF.isFriendsRoom(data.game_type) then
        self:_addInfoItem(_T("LAB_INFO_046"), data.play_times)
        self:_addInfoItem(_T("LAB_INFO_047"), data.win_play_times)
        self:_addInfoItem(_T("LAB_INFO_048"), _N(data.profit))
        self.ItemGameNum:SetActive(false)
        self.InfoView.transform.localPosition = bee.v3(self.InfoViewPos.x, self.InfoViewPos.y + 40)

        self.MaxWinCardtype:SetActive(true)
        self:refreshCardType(data.max_profit_cards, self.MaxWinCardtype)
        self.Trend:SetActive(false)
    elseif GF.isSNG(data.game_type) then
        self:_addInfoItem(_T("LAB_INFO_049"), data.tour_round)
        self:_addInfoItem(_T("LAB_INFO_050"), data.tour_win_round)
        self:_addInfoItem(_T("LAB_INFO_051"), _N(data.tour_max_profit))
        self:_addInfoItem(_T("LAB_INFO_052"), _N(data.tour_profit))
        self.ItemGameNum:SetActive(true)
        self:find("information_icon_title_01", self.ItemGameNum):SetActive(false)
        self:find("information_icon_title_02", self.ItemGameNum):SetActive(true)
        self.InfoView.transform.localPosition = self.InfoViewPos

        bee.setText(self.TextGameNum, data.champion_points)

        self.MaxWinCardtype:SetActive(false)

        self.Trend:SetActive(true)
        self:refreshTrend()
        Net:post("/player/sngRecord", {player_uid = self._uid}, function(resp)
            if not bee.isNull(self.node) and 0 == resp.code then
                self._sng_list = resp.list
                self:refreshTrend()
            end
        end)
    end
    self:refreshCardType(data.best_cards, self.MaxCardtype)

    self:_refreshRate(data.pool_entry_rate, self.Rates[1], 20, 28)
    self:_refreshRate(data.add_before_flipping_rate, self.Rates[2], 15, 25)
    self:_refreshRate(data.three_bet_rate, self.Rates[3], 7, 13)
    self:_refreshRate(data.show_hand_rate, self.Rates[4], 20, 30)
    self:_refreshRate(data.active_rate, self.Rates[5], 30, 50)
    self:_refreshRate(data.c_bete_rate, self.Rates[6], 40, 75)
end

function P:_addInfoItem(name, value)
    local item = CU.GameObject.Instantiate(self.InfoItem1, self.InfoView.transform, false)
    item:SetActive(true)
    bee.setText(self:find("TextName", item), name)
    bee.setText(self:find("TextNum", item), value)
end

function P:_refreshRate(rate, item, low, hight)
    bee.setText(self:find("TextNum", item), "" .. math.round((rate or 0) / 10) / 10 .. "%")
    local fill = self:find("CircleSlider/information_new_slider_fill_01", item)
    bee.setFillAmount(fill, rate / 10000)
end

function P:refreshCardType(data, item)
    if not data or data.profit <= 0 then
        self:find("TextEmpty", item):SetActive(true)
        self:find("Win", item):SetActive(false)
    else
        self:find("TextEmpty", item):SetActive(false)
        self:find("Win", item):SetActive(true)

        bee.setText(self:find("Win/TextTitle", item), GameModel:getReplayTitle({
            game_type = self._game_type, tour_name = data.tour_name, small_blind = data.sb, big_blind = data.bb, game_start_time = data.time}))
        bee.setText(self:find("Win/TextWin", item), _N(data.profit))
        
        if data.cards and (self._uid == PlayerModel:getUid() or #data.cards >= 5) then
            for i = 1, 5 do
                bee.setIcon(self:find("Win/card" .. i, item), GF.getCardImageByCode(data.cards[i] or 0))
            end
            if #data.cards == 4 then
                local _, cardType, _ = PKHelper.getOmahaType(data.cards, nil)
                bee.setText(self:find("Win/TextCardType", item), _T(cardType))
            else
                local public_cards = {}
                for i = 3, 5 do
                    if data.cards[i] and data.cards[i] ~= 0 then
                        table.insert(public_cards, data.cards[i])
                    end
                end
                local _, cardType, _ = PKHelper.getHoldemType({data.cards[1], data.cards[2]}, public_cards)
                bee.setText(self:find("Win/TextCardType", item), _T(cardType))
            end
            self:find("Win/ingame_replay_card_type_01", item):SetActive(true)
        else
            for i = 1, 5 do
                local code = data.board and data.board[i] or 0
                bee.setIcon(self:find("Win/card" .. i, item), GF.getCardImageByCode(code))
            end
            self:find("Win/ingame_replay_card_type_01", item):SetActive(false)
            bee.setText(self:find("Win/TextCardType", item), "")
        end
    end
end

function P:refreshTrend()
    bee.setText(self:find("Session/TextCount", self.Trend), _F("LAB_INFO_066", self._sng_count))
    self:find("Session/common_slider_02_button_plus", self.Trend):SetActive(self._sng_count_index < #self._sng_count_list)
    self:find("Session/common_slider_02_button_minus", self.Trend):SetActive(self._sng_count_index > 1)

    self:removeAllChildren(self.TrendView)
    if not self._sng_list then
        return
    end
    local index = #self._sng_list - self._sng_count + 1
    local num = self._sng_count
    if index < 1 then
        index = 1
        num = #self._sng_list
    end

    local s = self.TrendView.transform.sizeDelta
    local w = s.x / (self._sng_count - 1)
    local pointPoses = {}
    for i = index, #self._sng_list do
        local v = self._sng_list[i]
        local point = CU.GameObject.Instantiate(self.TrendPoint, self.TrendView.transform, false)
        point:SetActive(true)
        local pos = bee.v3(-s.x/2 + (i - index) * w, (2 - v) * s.y / 2)
        point.transform.localPosition = pos
        table.insert(pointPoses, pos)
        if i > index then
            local line = CU.GameObject.Instantiate(self.TrendLine, self.TrendView.transform, false)
            line:SetActive(true)
            local p1 = pointPoses[#pointPoses - 1]
            line.transform.localPosition = bee.v3((p1.x + pos.x) / 2, (p1.y + pos.y) / 2)
            
            local angle = bee.v3SignedAngle(CU.Vector3.right, bee.v3(pos.x - p1.x, pos.y - p1.y), CU.Vector3.forward)
            line.transform.localEulerAngles = bee.v3(0, 0, angle)
            local length = bee.v3Distance(p1, pos)
            local lineSize = line.transform.sizeDelta
            lineSize.x = length
            line.transform.sizeDelta = lineSize
        end
    end
end

function P:setFavoriteSkins(skins)
    for k, v in ipairs(skins) do
        local d = tpl_character_skin[v.skin_id]
        local lvl = v.bond_level
        if self._uid == PlayerModel:getUid() then
            local r = CharacterModel:getRole(d.role)
            if r then
                lvl = r:getBondLevel()
            end
        end
        self.BgAvatars[k]:SetActive(true)
        local item = CU.GameObject.Instantiate(self.Item1, self.BgAvatars[k].transform, false)
        item.transform.localPosition = bee.v3zero
        item:SetActive(true)
        bee.setText(self:find("TextLevel", item), CharacterModel:getBondLevelStr(lvl))
        if d then
            bee.setIcon(self:find("Avatar/Mask/ImageIcon", item), PlayerModel:getAvatarIcon(d.avatar))
        end
        -- if self._uid == PlayerModel:getUid() and not self._hideOperate then
        --     bee.addClick(item, function()
        --         UiManager:showUI("InformationAvatarDetail")
        --     end)
        -- else
        --     item:GetComponent("ButtonZoom").enabled = false
        -- end
    end
    if self._uid == PlayerModel:getUid() and not self._hideOperate then
        self.TextEmpty:SetActive(false)
    else
        self.TextEmpty:SetActive(#skins == 0)
        for i = #skins + 1, 4 do
            self.BgAvatars[i]:SetActive(false)
        end
    end
end

function P:refreshAchievement(data)
    if data then
        for _, v in ipairs(data.counts) do
            if self.TextAchievements[v.level] then
                bee.setText(self.TextAchievements[v.level], v.num)
            end
        end
    else
        for k, v in ipairs(self.TextAchievements) do
            bee.setText(v, AchievementModel:getTotalNum(k))
        end
    end
end

function P:evt_EditFavoriteRoleRSP(msg)
    -- self:removeAllChildren(self.BgAvatar)
    for _, v in ipairs(self.BgAvatars) do
        self:removeAllChildren(v)
    end
    PlayerModel:sortFavoriteRoles()
    self:setFavoriteSkins(PlayerModel:getFavoriteRoles())
end

function P:evt_GetOtherDetailInfoRSP(msg)
    if msg.brief.uid == self._uid then
        bee.setText(self.TextName, msg.brief.name)
        bee.setText(self.TextLevel, msg.brief.level)
        bee.setIcon(self:find("Rank/icon_rank_01", self.Info1), tpl_level[msg.brief.level].icon)
        bee.setIcon(self:find("Mask/ImageIcon", self.Avatar), PlayerModel:getAvatarIcon(msg.brief.avatar))
        GF.setTitleImage(self.ImageTitle, msg.brief.title)
        GF.setFrameImage(self.ImageFrame, msg.brief.frame)
        bee.setText(self.TextDec, msg.declaration)
        self:setFavoriteSkins(msg.favorite_roles)
        self:refreshAchievement(msg)

        bee.setText(self.TextCollects[1], msg.collections.characters)
        bee.setText(self.TextCollects[2], msg.collections.outfits)
        bee.setText(self.TextCollects[3], msg.collections.decorations)
        bee.setText(self.TextCollects[4], msg.collections.titles)

        self.other_skin_id = msg.skin_id
        local skin = tpl_character_skin[self.other_skin_id]
        if skin then
            self.CharacterImage:SetActive(true)
            bee.invoke(self.CharacterImage, "setSkinImage", skin)
        end

        bee.removeAllClick(self.CertificationIcon)
        if msg.auth_cert_url and msg.auth_cert_url ~= "" then
            bee.setText(self.CertificationText, _T("LAB_SEVEN_DAY_TASKS_DEC_32"))
        else
            bee.setText(self.CertificationText, _T("LAB_SEVEN_DAY_TASKS_DEC_31"))
        end
        if msg.auth_cert_url and msg.auth_cert_url ~= "" then
            bee.addClick(self.CertificationIcon, function()
                local info = {
                    name = msg.brief.name,
                    uid = self._uid,
                    register_time = msg.register_time,
                    auth_cert_time = msg.auth_cert_time,
                    auth_cert_url = msg.auth_cert_url,
                }
                UiManager:showUI("SevenDayTaskCertification", {info = info, isFromTable = self._fromTable})
            end)
            bee.setBtEnable(self.CertificationIcon, true)
            self.CertificationIcon:GetComponent("ButtonZoom").enabled = true
        else
            bee.setGrey(self.CertificationIcon, true)
            self.CertificationIcon:GetComponent("ButtonZoom").enabled = false
            -- bee.addClick(self.CertificationIcon, function()
            --     UiManager:showToast(_T("LAB_SEVEN_DAY_TASKS_TIPS_4"))
            -- end)
        end
    end
end

function P:evt_ChangeAvatarRSP(msg)
    if self._uid == PlayerModel:getUid() then
        bee.setIcon(self:find("Mask/ImageIcon", self.Avatar), PlayerModel:getAvatarIcon())
    end
end

function P:evt_ChangeFrameRSP(msg)
    if self._uid == PlayerModel:getUid() then
        GF.setFrameImage(self.ImageFrame, PlayerModel:getFrame())
    end
end

function P:evt_ChangeTitleRSP(msg)
    if self._uid == PlayerModel:getUid() then
        GF.setTitleImage(self.ImageTitle, PlayerModel:getTitle())
    end
end

function P:evt_refreshName()
    if self._uid == PlayerModel:getUid() then
        bee.setText(self.TextName, PlayerModel:getName())
    end
end

function P:evt_refreshDeclaration()
    if self._uid == PlayerModel:getUid() then
        bee.setText(self.TextDec, PlayerModel:getDeclaration())
    end
end

function P:evt_SetBlockChatRSP(msg)
    if 0 == msg.code and msg.is_block then
        UiManager:showToast(_T("LAB_INFO_042"))
    end
end

function P:evt_updateScheme(msg)
    bee.invoke(self.CharacterImage, "setSkinImage", CharacterModel:getUsingRole():getSkinData())
end

function P:evt_SwitchRoleSkinRSP(msg)
    self:evt_updateScheme()
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

function P:evt_shareShot()
    self.BackButton:SetActive(false)
    self.CopyButton:SetActive(false)
    self.Edit_01_Button:SetActive(false)
    self.Edit_02_Button:SetActive(false)
    self.Edit_03_Button:SetActive(false)
    self.Edit_04_Button:SetActive(false)
    self.ZoomButton:SetActive(false)
    self.ShareCont:SetActive(false)

    self.AnimRoot.transform.localPosition = bee.v3(0, 50, 0)

    local skins = PlayerModel:getFavoriteRoles()
    if not skins or #skins == 0 then
        self.TextEmpty:SetActive(true)
        for k,v in pairs(self.BgAvatars) do
            v:SetActive(false)
        end
    end
end

function P:evt_endShareShot()
    self.AnimRoot.transform.localPosition = bee.v3(0, 0, 0)
    self.BackButton:SetActive(true)
    self.CopyButton:SetActive(true)
    for k,v in pairs(self.BgAvatars) do
        v:SetActive(true)
    end
    self:onShow()
end

function P:evt_updateSharedPage()
    self:setShareCont()
end

function P:evt_updateMonthlyCard()
    self.InfoUnlock:SetActive(ShopModel:isMonthlyCard())
    self.InfoLock:SetActive(not ShopModel:isMonthlyCard())
end

function P:setShareCont()
    local ShareReward = self:find("ShareReward", self.ShareCont)
    local Icon = self:find("Icon", ShareReward)
    local CountText = self:find("CountText", ShareReward)
    ShareModel:setShareCont(ShareReward, Icon, CountText, 1)
end

--引导
function P:infoGuide()
    if bee.isInHome() then
        GuideManager:startSystemGuide(9001, 0.65)
    end
end

return P