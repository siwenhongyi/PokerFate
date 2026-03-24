local P = class("LobbyLayer", UiBase)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_LobbyLayer_into", "UI_1_LobbyLayer_back"

    self.AnimRoot = self:find("AnimRoot")
    local Center = self:find("Center", self.AnimRoot)
    local LeftTop = self:find("LeftTop", self.AnimRoot)
    local RightTop = self:find("RightTop", self.AnimRoot)
    local Right = self:find("Right", self.AnimRoot)
    local RightBottom = self:find("RightBottom", self.AnimRoot)
    local LeftBottom = self:find("LeftBottom", self.AnimRoot)

    self.ImageBg = self:find("ImageBg", self.AnimRoot)
    
    self.MaskFront = bee.find("UIRoot/UiCanvaPost/MaskFront")
    if not self.MaskFront then
        self.MaskFront = self:find("MaskFront")
    end
    self.MaskFront:SetActive(false)

    self.CharacterImage = self:find("CharacterImage", Center)
    self.CharacterImage:SetActive(false)
    self.BubbleParent = self:find("BubbleParent", Center)
    self.BubbleItem = self:find("BubbleItem", self.BubbleParent)

    self.ShopPushButton = self:find("Left/ShopPushButton", LeftTop)
    self.SevenDayTaskButton = self:find("Left/SevenDayTaskButton", LeftTop)
    self.UpdateButton = self:find("Top/UpdateButton", LeftTop)
    self.ActivityButton = self:find("Left/ActivityButton", LeftTop)
    self.SideGameTips = self:find("SideGameTips", LeftTop)
    self.TaskButton = self:find("Left/TaskButton", LeftTop)
    self.ActButton = self:find("Left/ActButton", LeftTop)
    self.HotspringButton = self:find("Left2/HotspringButton", LeftTop)
    self.GalaSeasonButton = self:find("Left2/GalaSeasonButton", LeftTop)
    self.SchoolButton = self:find("Left2/SchoolButton", LeftTop)
    self.SpringFestivalButton = self:find("Left2/SpringFestivalButton", LeftTop)

    RedManager:bind(self:find("RedPoint", self.ActivityButton), RedTag.Pinball)
    RedManager:bind(self.SideGameTips, RedTag.Pinball)

    self.Character = self:find("Character", LeftTop)
    self.TextLevel = self:find("TextLevel", self.Character)
    self.TextName = self:find("TextName", self.Character)
    self.ExpSlider = self:find("ExpSlider", self.Character)
    self.Avatar = self:find("Avatar", self.Character)
    self.TitleIcon = self:find("TitleIcon", self.Character)
    self.ImageUserType = self:find("ImageUserType", self.Character)
    if self.ImageUserType then
        self.ImageUserType:SetActive(false)
    end

    self.SettingButton = self:find("SettingButton", RightTop)
    self.MailButton = self:find("MailButton", RightTop)
    self.NoticeButton = self:find("NoticeButton", RightTop)
    self.Gold = self:find("Currency/Gold", RightTop)
    self.Ticket1 = self:find("Currency/Ticket1", RightTop)

    self.PokerButton = self:find("PokerButton/PokerButton", Right)
    self.OmahaButton = self:find("OmahaButton", Right)
    self.CharacterButton = self:find("CharacterButton/CharacterButton", Right)
    self.GachaButton = self:find("GachaButton/GachaButton", Right)
    self.FriendGameButton = self:find("FriendGameButton", Right)
    self.TournamentButton = self:find("TournamentButton/TournamentButton", Right)

    local LeftBottomList = self:find("LeftBottomList", LeftBottom)
    self.CustomizationButton = self:find("CustomizationButton", LeftBottomList)
    self.UIVisibleButton = self:find("UIVisibleButton", LeftBottomList)
    self.ExplosionButton = self:find("ExplosionButton", LeftBottomList)
    self.ClickMask = self:find("ClickMask")
    self.ClickMask:SetActive(false)

    bee.addClick(self.ClickMask, function()
        self:onClickMask()
    end)

    bee.addClick(self.CustomizationButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("LobbyCustomization")
    	bee.logEvent("lobby-custom")
    end)

    RedManager:bind(self:find("RedPoint", self.TaskButton), RedTag.Task)

    bee.addClick(self.Character, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("InformationMain", {from = "lobby"})
    	bee.logEvent("profile-lobby")
    end)

    bee.addClick(self.PokerButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("OmahaBlinds", {gameType = GAME_GAME_TYPE.LOBBY_HOLDEM_GAME})
        bee.logEvent("lobby-poker")
    end)

    bee.addClick(self.OmahaButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("OmahaBlinds", {gameType = GAME_GAME_TYPE.LOBBY_OMAHA_GAME})
        bee.logEvent("lobby-omaha")
    end)

    bee.addClick(self.CharacterButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterMain")
        bee.logEvent("character-lobby")
    end)

    bee.addClick(self.GachaButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("GachaMain")
    end)

    bee.addClick(self.FriendGameButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("FriendsRoom")
        bee.logEvent("friendsroom-lobby")
    end)

    bee.addClick(self.TournamentButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("TournamentLobby")
        bee.logEvent("lobby-tournament")
    end)

    bee.addClick(self.NoticeButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("Notice")
        bee.logEvent("notice-lobby")
    end)

    bee.addClick(self.SettingButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("Setting")
        bee.logEvent("lobby-setting")
    end)

    bee.addClick(self.MailButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("EmailMain")
        bee.logEvent("mail-lobby")
    end)

    bee.addClick(self.ShopPushButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("ShopPushView")
        bee.logEvent("lobby-newpresident-outfit-icon")
    end)
    bee.addClick(self.SevenDayTaskButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SevenDayTask")
        bee.logEvent("7daytask-lobby")
    end)

    bee.addClick(self.ActivityButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        -- UiManager:showUI("ColorGame")
        bee.logEvent("lobby-casual-games")
        UiManager:showUI("SideGameView")
    end)
    bee.addClick(self.ExplosionButton, function()
        Game:playSound("ui_button_confirm")
        self:onClickExplosionButton()
    end)
    bee.addClick(self.UIVisibleButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        self:onClickUIVisibleButton()
    end)

    bee.addClick(self.HotspringButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("onsen-lobby")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self.HotspringButton:SetActive(false)
            return
        end
        self:stopRoleInteraction()
        UiManager:showUI("HotSpringHall")
        bee.logEvent("lobby-hot-spring")
    end)

    bee.addClick(self.GalaSeasonButton, function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self.GalaSeasonButton:SetActive(false)
            return
        end
        self:stopRoleInteraction()
        UiManager:showUI("GalaSeasonMain")
        bee.logEvent("galaseason-lobby")
    end)

    bee.addClick(self.SchoolButton, function()
        Game:playSound("ui_button_confirm")
        if not ThemeModel:isActivityOpen() then
            UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
            self.SchoolButton:SetActive(false)
            return
        end
        self:stopRoleInteraction()
        UiManager:showUI("SchoolMain")
    end)

    bee.addClick(self.SpringFestivalButton, function()
        Game:playSound("ui_button_confirm")
        self:stopRoleInteraction()
        UiManager:showUI("SpringFestivalMain")
        bee.logEvent("springfestival-lobby")
    end)

    bee.addClick(self.UpdateButton, function()
        local params =
        {
            button = 2,
            title = _T("LAB_UPDATE_TITILE_1"),
            text = _F("LAB_UPDATE_TIPS_2", "<color=#EC0B7A>" .. tostring(AppLoadRes:getMB(AppLoadRes.downSize)) .. "</color> MB"),
            surStr = _T("LAB_UPDATE_BTN_3"),
            cancelStr = _T("LAB_UPDATE_BTN_1"),
            onSure = function()
                G_DOWNLOAD_REMOTE = true
                bee.enterScene("StartScene")
            end,
            onCancel = function()
            end
        }
        Game:playSound("ui_button_confirm")
        self:stopRoleInteraction()
        UiManager:showUI("UpdateVersion", params)
		RedManager:removeTag(RedTag.UpdateTag)
    end)

    local BottomToggle = self:find("BottomToggle", RightBottom)
    bee.addClick(self:find("BackpackToggle", BottomToggle), function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BackpackMain")
        bee.logEvent("backpack-lobby")
    end)
    bee.addClick(self:find("CardsToggle", BottomToggle), function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("IngameReplay")
    end)
    bee.addClick(self:find("RankingToggle", BottomToggle), function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        bee.logEvent("leaderboard-lobby")
        UiManager:showUI("RankingMain")
    end)
    bee.addClick(self:find("FriendsToggle", BottomToggle), function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("Friend")
        bee.logEvent("friends-lobby")
    end)
    bee.addClick(self:find("ShopToggle", BottomToggle), function()
        self:stopRoleInteraction()
        bee.logEvent("shop-lobby")
        UiManager:showUI("Shop")
    end)

    bee.addClick(self.TaskButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("TaskView")
        bee.logEvent("lobby-task")
    end)

    bee.addClick(self.ActButton, function()
        self:stopRoleInteraction()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("ActivityMain")
        bee.logEvent("lobby-activity")
    end)

    local FriendRedPoint = self:find("FriendsToggle/RedPoint", BottomToggle)
    RedManager:bind(FriendRedPoint, RedTag.Friends)

    local ShopRedPoint = self:find("ShopToggle/RedPoint", BottomToggle)
    RedManager:bind(ShopRedPoint, RedTag.Shop)
    local ShopNewTag = self:find("ShopToggle/NewTag", BottomToggle)
    RedManager:bind(ShopNewTag, RedTag.ShopNewOut)
    
    RedManager:bind(self:find("BackpackToggle/RedPoint", BottomToggle), RedTag.Backpack)

    RedManager:bind(self:find("Reddot", self.MailButton), RedTag.Email)
    RedManager:bind(self:find("Reddot", self.NoticeButton), RedTag.Notice)
    RedManager:bind(self:find("RedPoint", self.SevenDayTaskButton), RedTag.SevenDayTask)
    RedManager:bind(self:find("RedPoint", self.ActButton), RedTag.Activity)
    RedManager:bind(self:find("Reddot", self.CharacterButton), RedTag.Character)
    RedManager:bind(self:find("Reddot", self.HotspringButton), RedTag.HotSpring)
    RedManager:bind(self:find("Reddot", self.GalaSeasonButton), RedTag.GalaSeason)
    RedManager:bind(self:find("Reddot", self.SchoolButton), RedTag.School)
    RedManager:bind(self:find("Reddot", self.SpringFestivalButton), RedTag.SpringFestival)
    RedManager:bind(self:find("RedPoint", self.UpdateButton), RedTag.UpdateTag)

    self.UpdateButton:SetActive(false)
    self.HotspringButton:SetActive(false)
    self.GalaSeasonButton:SetActive(false)
    self.SchoolButton:SetActive(false)
    self.SpringFestivalButton:SetActive(false)

    self.ShopPushButton:SetActive(#ShopModel:getShopPushList() > 0)

    local sdtStatus = SevenDayTaskModel:getCurUnlockChapterStatus()
    self.SevenDayTaskButton:SetActive(sdtStatus and sdtStatus ~= SevenDayTaskStatus.Upload)
end

function P:onStart()
    bee.invoke(self.Gold, "setItemId", GPropId.Gold)
    bee.invoke(self.Gold, "setClickCallback", function()
        bee.logEvent("lobby-chips")
    end)
    bee.invoke(self.Ticket1, "setItemId", GPropId.TicketDraw)
    bee.invoke(self.Ticket1, "setClickCallback", function()
        bee.logEvent("lobby-roulette-crystal")
    end)

    -- 每秒检查限时活动图标是否显示或关闭
    self._limitButtons = {
        [self.HotspringButton] = ActivityId.HotSpring,
        [self.GalaSeasonButton] = ActivityId.GalaSeason,
        [self.SchoolButton] = ActivityId.School,
    }
    self:schedule(1, function()
        self:checkActivityButtons()
    end)
end

function P:onShow()
    self:evt_refreshUpdateInfo()
    self:evt_refreshTopInfo()
    self:evt_refreshLevel()
    self:evt_refreshName()
    self:evt_refreshAvatar()
    self:evt_ChangeFrameRSP()
    self:evt_ChangeTitleRSP()
    self:evt_refreshSysunlock()

	if self.ImageUserType then
		if USER_TYPE.Developer == PlayerModel:getUserType() then
			self.ImageUserType:SetActive(true)
			bee.setIcon(self.ImageUserType, "InGame[ingame_player_other03_developer]")
		elseif USER_TYPE.Streamer == PlayerModel:getUserType() then
			self.ImageUserType:SetActive(true)
			bee.setIcon(self.ImageUserType, "InGame[ingame_player_other02_streamer]")
		else
			self.ImageUserType:SetActive(false)
		end
	end

    self:evt_initScheme()
    -- self:setLobbySceneImg()
    -- self:setCharacterImage()

    self._inBlurs = {}  -- 处于背景模糊的 ui 列表

    GameModel:setData(nil, nil)

    self:refreshColorGame()
    self:checkActivityButtons()

	if GuideManager:isInGuide() then
		UiManager:showUI("GameGuide", {guide = GuideManager.curGuide.guide, data = GuideManager.curGuide})
    elseif GuideManager:checkGuide() then
        GuideManager:startGuide()
        return
    end

    -- 进入大厅后请求角色数据
    CharacterModel:requestGetSkinGameDetail()
end

function P:checkActivityButtons()
    for k, v in pairs(self._limitButtons) do
        k:SetActive(ActivityManager:isActivityOpen(ActivityId.Theme, v))
    end

    local sdtStatus = SevenDayTaskModel:getCurUnlockChapterStatus()
    self.SevenDayTaskButton:SetActive(sdtStatus and sdtStatus ~= SevenDayTaskStatus.Upload)

    local sfStatus = SpringFestivalModel:isActivityOpen()
    self.SpringFestivalButton:SetActive(sfStatus)
    if sfStatus then
        local timeText = self:find("CountDown/Text", self.SpringFestivalButton)
        SpringFestivalModel:getRemainTime(timeText, self.node)
    end
end

function P:evt_refreshSevenDayTask()
    local sdtStatus = SevenDayTaskModel:getCurUnlockChapterStatus()
    self.SevenDayTaskButton:SetActive(sdtStatus and sdtStatus ~= SevenDayTaskStatus.Upload)
end

function P:afterShow()
    if GuideManager:isInGuide() then
        return
    end

    self:tryAutoPop()
    self:characterGreeting()

    GF.dealDeepLinkParams()

    -- 再次请求数据，避免登录时请求失败，需要模块自行处理重复请求的问题
    self:once(3, function()
        ActivityManager:reqActivityData()
        SpringFestivalModel:reqActivityData()
    end)

    if not self._params or self._params.from ~= "StartScene" then
        self:evt_requestUpdateInfo()
    end
end

function P:tryAutoPop()
    SettingModel:checkAutoPop()
    if GameModel.over_bond_settle_info and GameModel.over_bond_settle_info.add_over_bond_inc > 0 then
            bee.showUiTask("IngameFeedback", {info = GameModel.over_bond_settle_info}, nil, LOBBY_POP_PRIORITY.BondUp)
    elseif GameModel.bond_settle_info and GameModel.bond_settle_info.win_hands > 0 then
        if GameModel.bond_settle_info.cur_bond_level >= Config.AWAKEN_LEVEL then
            if LocalStore:isTagValid("IngameBondsUp_fullpop_" .. CharacterModel:getUsingRoleId()) then
                bee.showUiTask("IngameBondsUp", {info = GameModel.bond_settle_info}, nil, LOBBY_POP_PRIORITY.BondUp)
            end
        else
            bee.showUiTask("IngameBondsUp", {info = GameModel.bond_settle_info}, nil, LOBBY_POP_PRIORITY.BondUp)
        end
    end
    GameModel.bond_settle_info = nil
    GameModel.over_bond_settle_info = nil

    --活动礼包弹窗
    self:festivalGiftpop()

    Net:sendReq("pb.BustProtectInfoREQ", {})

    PayHelper:checkPurchase()
    
    ActivityNewmanCheckinModel:checkAutoPop()
    SignInModel:checkSignIn()
    NoticeModel:tryAutoPop()
    if GameModel.summary and GameModel.summary.profit > 0 then
        if ShopModel:isShowShopPush() then
            bee.showUiTask("ShopPushView", {isAuto = true}, nil, LOBBY_POP_PRIORITY.ShopPush)
        end
        if GameModel.summary.profit >= tpl_constdata.Score_Profit * GameModel:getBigBlind() then
            SdkHelper:startAppReview()
        end
    end
    bee.runTask()
end

--活动礼包弹窗
function P:festivalGiftpop()
    if not LocalStore:isDailyTagValid("festival_gift_" .. PlayerModel:getUid()) then
        return
    end

    local sfStatus = SpringFestivalModel:isActivityOpen()
    if sfStatus then
        local popable = false
        for _,v in pairs(tpl_shop_activity_gifts) do
            local buyCount = ShopModel:getLimitGoodsBoughtCount(v.shop_type, v.buy_id)
            if buyCount < v.limit_count then
                popable = true
                break
            end
        end
        if popable then
            bee.showUiTask("SpringFestivalShop", {isAuto = true}, nil, LOBBY_POP_PRIORITY.FestivalGift)
        end
    end
end

function P:refreshColorGame() 
    self.ActivityButton:SetActive(SettingModel:isColorGameUnlock())
end

function P:evt_updateShopLimit()
    self.ShopPushButton:SetActive(#ShopModel:getShopPushList() > 0)
end

function P:evt_refreshLevel()
    bee.setText(self.TextLevel, PlayerModel:getCurLevel())
    bee.setSliderValue(self.ExpSlider, PlayerModel:getExpPercent())
    bee.setIcon(self:find("icon_rank_01", self.Character), tpl_level[PlayerModel:getCurLevel()].icon)
end

function P:evt_ExpChangeRSP()
    self:evt_refreshLevel()
    self:refreshColorGame()
end

function P:evt_refreshTopInfo()
    bee.invoke(self.Gold, "setCount", _N(PlayerModel:getGold()))
    bee.invoke(self.Ticket1, "setCount", _N(ItemModel:getItemNumById(GPropId.TicketDraw)))
end

function P:evt_refreshName()
    bee.setText(self.TextName, PlayerModel:getName())
end

function P:evt_refreshAvatar()
    local avatar = PlayerModel:getAvatarIcon()
    if avatar then
        bee.setIcon(self:find("Mask/ImageIcon", self.Avatar), avatar)
    end
end

function P:evt_ChangeFrameRSP(msg)
    GF.setFrameImage(self:find("ImageFrame", self.Avatar), PlayerModel:getFrame())
end

function P:evt_ChangeTitleRSP(msg)
    GF.setTitleImage(self.TitleIcon, PlayerModel:getTitle())
end

function P:evt_refreshLobbyMusic()
	bee.stopSound()
	Game:playLobbyBGM()
end

function P:evt_uiBlur(flag, name)
    self:evt_backgroundBlur(flag, name)
end

function P:evt_backgroundBlur(flag, name)
    if flag then
        self._inBlurs[name] = name
    else
        self._inBlurs[name] = nil
    end
    -- self._isInBlur = flag
    if flag then
        if not self._isInBlur then
            self._isInBlur = true

            self.transform:SetParent(bee.find("UIRoot/UiCanvaPost").transform, false)
            local camera = bee.find("UIRoot/CameraRoot/UiCameraPost")
            CS.Utils.SetPostKawaseBlur(camera, 0, 5, 1, 10, 0.25)
            
            -- self.MaskFront:SetActive(true)
            -- bee.setOpacity(self.MaskFront, 0)
            -- bee.tween(self.MaskFront)
            -- : to(0.25, {opacity = 0.6})
            -- : link()

            bee.Tween.killByTarget(self.MaskFront)

            if self._closeAnim then
                self:find("AnimRoot"):GetComponent("Animator"):Play(self._closeAnim, -1, 0)
            end
        end
    else
        self:once(-1, function()
            if self._isInBlur and not next(self._inBlurs) then
                self._isInBlur = false

                self.MaskFront:SetActive(true)
                bee.setOpacity(self.MaskFront, 0)
                bee.tween(self.MaskFront)
                : predelay(0.1)
                : call(function()
                    local camera = bee.find("UIRoot/CameraRoot/UiCameraPost")
                    CS.Utils.SetPostKawaseBlur(camera, 5, 0, 10, 1, 0.25)
                end)
                : to(0.25, {opacity = 0})
                : onComplete(function()
                    self.transform:SetParent(UiManager:getUiRoot().transform, false)
                    self.MaskFront:SetActive(false)
                end)
                : link()
                : setTarget()

                self:once(0.25, function()
                    if self._openAnim and not self._isInBlur then
                        self:find("AnimRoot"):GetComponent("Animator"):Play(self._openAnim, -1, 0)
                    end
                end)
            end
        end)
    end
end

function P:evt_SelfUserInfoRSP(msg)
    self:evt_refreshTopInfo()
    self:evt_refreshLevel()
    bee.setText(self.TextName, PlayerModel:getName())

    SettingModel:checkNewUnlockSys()
end

function P:evt_UnlockNewModuleRSP(msg)
    if #msg.success_ids > 0 then
        for k, v in ipairs(msg.success_ids) do
            bee.showUiTask("LevelUnlock", {ids = {v}}, nil, LOBBY_POP_PRIORITY.SysOpen)
        end
        bee.runTask()
    end
end

function P:evt_refreshLobbyRole()
    self:setCharacterImage()
end

function P:evt_initScheme()
    if not PlayerModel:getCurSchemeId() then
        Game:stopMusic()
        self.CharacterImage:SetActive(false)
        return
    end
    self.CharacterImage:SetActive(true)
    
    self:setCharacterImage()
    self:setLobbySceneImg()
    self:setLobbyMusic()
end

function P:evt_updateScheme(scheme)
    if scheme and scheme.scheme_id ~= PlayerModel:getCurSchemeId() then
        return
    end

    self:setCharacterImage()
    self:setLobbySceneImg()
end

function P:evt_changeScheme()
    self:setCharacterImage()
    self:setLobbySceneImg()
end

function P:setCharacterImage()
    local schemeInfo = PlayerModel:getCurScheme()
    if not schemeInfo then
        return
    end

    local skinId = schemeInfo.skin_id
    local skinCfg = tpl_character_skin[skinId]
    local role = CharacterModel:getRole(skinCfg.role)
    if role then
        self.characterCls = ObjectPool:getCls(self.CharacterImage)
        self.characterCls:setRole(role)
        self.characterCls:setSkin(skinCfg)
        self.characterCls:setBubbleItem(self.BubbleItem)
        self.characterCls:initSpecialInteraction(function()
            TaskModel:reportTask(TaskType.RoleInteraction)
        end)
        self.characterCls:initLobbyClickVoice(function()
            TaskModel:reportTask(TaskType.RoleInteraction)
        end)
        self.characterCls:initAccessoriesInteraction()

        self:stopRoleInteraction()
        if self._bubbleTag then
            scheduler:removeTag(self._bubbleTag)
            self._bubbleTag = nil
            self.Bubble:SetActive(false)
        end
    end

    if schemeInfo.property_list and schemeInfo.property_list[1] then
        local x = schemeInfo.property_list[1] / 10
        local y = schemeInfo.property_list[2] / 10
        local size = schemeInfo.property_list[3] / 100
        self.CharacterImage.transform.localPosition = bee.v3(x, y, 0)
        self.CharacterImage.transform.localScale = bee.v3(size, size, 1)
    else
        self.CharacterImage.transform.localPosition = bee.v3(PlayerModel.CharacterDefaultPosX, PlayerModel.CharacterDefaultPosY, 0)
        self.CharacterImage.transform.localScale = bee.v3(PlayerModel.CharacterDefaultPosSize, PlayerModel.CharacterDefaultPosSize, 1)
    end

    if skinCfg.spine_rotation then
        self.CharacterImage.transform.localEulerAngles = bee.v3(0, 0, skinCfg.spine_rotation)
    else
        self.CharacterImage.transform.localEulerAngles = bee.v3zero
    end
end

function P:setLobbyMusic()
    if self._playedLobbyBgm then
        return
    end
    local schemeInfo = PlayerModel:getCurScheme()
    if not schemeInfo then
        return
    end
    Game:playLobbyBGM()
    self._playedLobbyBgm = true
end

-- 角色打招呼
function P:characterGreeting()
    if PlayerModel:isPlayedGreeting() then
        return
    end
    if not self.characterCls then
        return
    end

    local schemeInfo = PlayerModel:getCurScheme()
    if not schemeInfo then
        return
    end
    local skinId = schemeInfo.skin_id
    local skinCfg = tpl_character_skin[skinId]
    local role = CharacterModel:getRole(skinCfg.role)

    PlayerModel:setGreetingFlag(true)
    bee.addTaskFunc(function()
        if role then
            local voiceCfg
            if role:isAwaken() then
                voiceCfg = role:getSkinData().awakened_greet_voice
            else
                voiceCfg = role:getSkinData().default_greet_voice
            end
            if voiceCfg then
                local chat = {sound = voiceCfg[1], face = voiceCfg[2], text = voiceCfg[3]}
                self.characterCls:playVoice(chat)
            end
        end
    end, 0, nil, LOBBY_POP_PRIORITY.RoleLoginVoice)
    bee.runTask()
end

function P:setLobbySceneImg()
    local cfg = tpl_hall_scene[PlayerModel:getCurLobbyScene()]
    if cfg then
        bee.setIcon(self.ImageBg, cfg.bg_image)
    end
end

function P:evt_refreshLobbyScene()
    self:setLobbySceneImg()
end

function P:evt_refreshUpdateInfo()
    if bee.compareVer(G_UPDATE_VERSION, G_REMOTE_VERSION) < 0 then
        self.UpdateButton:SetActive(true)
    else
        self.UpdateButton:SetActive(false)
    end
end

function P:evt_requestUpdateInfo()
    G_CHECK_FORCE_UPDATE = true
    AppLoadRes:checkUpdate(false, false, function()
    end)
end

function P:evt_BustProtectInfoRSP(msg)
    if msg.reward_chips > 0 then
        bee.showUiTask("IngameBankrupt", {msg = msg}, nil, LOBBY_POP_PRIORITY.Bankrupt)
        bee.runTask()
    end
end

function P:evt_try_auto_pop()
    self:once(1, function()
        self:tryAutoPop()
    end)
end

function P:evt_lan_mod()
    self:evt_ChangeTitleRSP()
end

function P:evt_refreshSysunlock()
    -- local id = SettingModel:getSysUnlockRed()
    -- if id then
    --     local data = tpl_system_info[id]
    --     if data and data.ui then
    --         local node = self:find(data.ui)
    --         if node then
    --             local obj = bee.createObj("views/Guide/GuideFinger")
    --             obj.transform:SetParent(self.AnimRoot.transform, false)
    --             obj.transform.position = node.transform.position
    --         end
    --     end
    -- end
end

function P:evt_PushGiftRSP(msg)
    if msg.code == 0 then
        local data = {quick_buy = msg.gift_id, gameType = msg.game_type}
        UiManager:showUI("IngameQuickBy", {data = data})
    end
end

function P:onClickExplosionButton()
    local schemeInfo = PlayerModel:getCurScheme()
    if not schemeInfo then
        return
    end
    local skinCfg = tpl_character_skin[schemeInfo.skin_id]
    local curCount = CharacterModel:getRoleSkinGameDetails(skinCfg.id)
    if CharacterModel:getRoleSkinGameDetails(skinCfg.id) < skinCfg.bust_limit then
        CharacterModel:requestGetSkinGameDetail()
        UiManager:showUI("LobbySkinNotice", {curCount = curCount, count = skinCfg.bust_limit})
        return
    end
    if not bee.checkCd("lobby_show_explosion", 2) then
        UiManager:showToast(_T("ERR_MSG_FREQUENT"))
        return
    end
    self:stopRoleInteraction()
    self._isExplosion = not self._isExplosion
    if self._isExplosion then
        bee.logEvent("lobby-character-bust-click", skinCfg.id)
        self.characterCls:playScrap()
    else
        self.characterCls:stopScrap()
    end
end

function P:onClickUIVisibleButton()
    self:playAnimator("UI_1_LobbyLayer_back")
    self.ClickMask:SetActive(true)

    local schemeInfo = PlayerModel:getCurScheme()
    local skinCfg = tpl_character_skin[schemeInfo.skin_id]
    bee.logEvent("lobby-character-ui-click", skinCfg.id)
end

function P:onClickMask()
    self:playAnimator("UI_1_LobbyLayer_into")
    self.ClickMask:SetActive(false)
end

-- 停止角色交互语音
function P:stopRoleInteraction()
    Game:stopRoleSound()
    if self.characterCls then
        self.characterCls:hideBubble()
        self.characterCls:switchIdle()
    end
end



