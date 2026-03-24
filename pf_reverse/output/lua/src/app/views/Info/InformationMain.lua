local P = class("InformationMain", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)

    self.CharacterImage = self:find("CharacterImage", self.Center)

    self.Tips = self:find("Tips", self.Center)
    self.Info1 = self:find("Info1", self.Center)
    self.Info2 = self:find("Info2", self.Center)
    self.Info3 = self:find("Info3", self.Center)
    self.Info4 = self:find("Info4", self.Center)
    self.Info5 = self:find("Info5", self.Center)

    self.Edit_01_Button = self:find("EditButton", self.Info1)
    self.Edit_02_Button = self:find("Edit_02_Button", self.Info1)
    self.CopyButton = self:find("CopyButton", self.Info1)
    self.TextName = self:find("TextName", self.Info1)
    self.TextUID = self:find("TextUID", self.CopyButton)
    self.ImageTitle = self:find("ImageTitle", self.Info1)
    self.TextLevel = self:find("Rank/TextLevel", self.Info1)
    self.Avatar = self:find("Avatar", self.Info1)
    self.ImageFrame = self:find("ImageFrame", self.Info1)
    self.CertificationIcon = self:find("Certification/CertificationIcon", self.Info1)
    self.CertificationText = self:find("Certification/CertificationText", self.Info1)

    self.Edit_03_Button = self:find("EditButton", self.Info2)
    self.TextDec = self:find("TextDec", self.Info2)

    self.Edit_04_Button = self:find("Edit_04_Button", self.Info3)
    self.TextEmpty = self:find("TextEmpty", self.Info3)
    self.BgAvatars = {
        self:find("BgAvatar1", self.Info3),
        self:find("BgAvatar2", self.Info3),
        self:find("BgAvatar3", self.Info3),
        self:find("BgAvatar4", self.Info3),
    }
    self.Item1 = self:find("Item1", self.Info3)
    self.Item1:SetActive(false)

    self.ZoomButton = self:find("ZoomButton", self.Center)
    self.AddFriendButton = self:find("AddFriendButton", self.RightTop)
    self.ReportButton = self:find("ReportButton", self.RightTop)
    self.ChatButton = self:find("ChatButton", self.RightTop)
    self.ShareCont = self:find("ShareCont", self.RightTop)
    self.ShareButton = self:find("ShareButton", self.ShareCont)
    self.ShareCont:SetActive(false)

    self.TextCollects = {
        self:find("Item1/TextNum", self.Info4),
        self:find("Item2/TextNum", self.Info4),
        self:find("Item3/TextNum", self.Info4),
        self:find("Item4/TextNum", self.Info4),
    }

    self.TextRecords = {
        self:find("Item1/TextNum", self.Info5),
        self:find("Item2/TextNum", self.Info5),
        self:find("Item3/TextNum", self.Info5),
        self:find("Item4/TextNum", self.Info5),
    }

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
end

function P:onShow()
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
        
        self:evt_SelfAchievementsRSP(PlayerModel:getAchievements())
        Net:sendReq("pb.SelfAchievementsREQ", {})

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

function P:evt_EditFavoriteRoleRSP(msg)
    -- self:removeAllChildren(self.BgAvatar)
    for _, v in ipairs(self.BgAvatars) do
        self:removeAllChildren(v)
    end
    PlayerModel:sortFavoriteRoles()
    self:setFavoriteSkins(PlayerModel:getFavoriteRoles())
end

function P:evt_SelfAchievementsRSP(msg)
    msg = msg.achievements or msg
    bee.setText(self.TextRecords[1], msg.holdem_firepower > 0 and msg.holdem_firepower or "-")
    bee.setText(self.TextRecords[2], msg.sng_champion > 0 and msg.sng_champion or "-")
    bee.setText(self.TextRecords[3], msg.mtt_champion > 0 and msg.mtt_champion or "-")
    bee.setText(self.TextRecords[4], msg.omaha_firepower > 0 and msg.omaha_firepower or "-")
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
        self:evt_SelfAchievementsRSP(msg.achievements)

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

