local P = class("CharacterMainProfile", require("app.views.Character.CharacterBase"))

function P:onAwake()
    P.super.onAwake(self)
	self._closeAnim = ""

    local Profile = self:find("Profile", self.Right)

    self.bg_character_bg_hellhound = self:find("bg_character_bg_hellhound", self.Center)
    self.TextName2 = self:find("TextName", Profile)

    -- self.ImageBgs = {
    --     self:find("character_profile_list_bg_01", Profile),
    --     self:find("character_profile_list_bg_02", Profile),
    --     self:find("character_profile_list_bg_03", Profile),
    -- }
    self.Info = self:find("Info", Profile)
    self.Voice = self:find("Voice", Profile)
    self.File = self:find("File", Profile)
    self.Views = {
        self.Info, self.Voice, self.File
    }

    self.TextCVInfo = self:find("TextCV", self.Info)
    self.TextCVVoice = self:find("TextCV", self.Voice)
    self.TextCVFile = self:find("TextCV", self.File)

    self.InfoList = self:find("InfoList", self.Info)
    self.VoiceList = self:find("VoiceList", self.Voice)
    self.FileList = self:find("FileList", self.File)
    self.Lists = {
        self.InfoList, self.VoiceList, self.FileList
    }

    local InfoContent = self:find("Viewport/Content", self.InfoList)
    self.InfoItem1 = self:find("InfoItem1", InfoContent)
    self.InfoItem2 = self:find("InfoItem2", InfoContent)
    self.InfoItem3 = self:find("InfoItem3", InfoContent)

    self.EmojiAnim = self:find("EmojiAnim", self.InfoItem2)
    self.EmojiAnim:SetActive(false)

    self.VoiceTitle = self:find("Title1", self.VoiceList)
    self.VoiceItem1 = self:find("VoiceItem1", self.VoiceList)
    self.VoiceTitle:SetActive(false)
    self.VoiceItem1:SetActive(false)

    self.Empty = self:find("Empty", self.File)
    self.FileItems = {
        self:find("Viewport/Content/FileCont/FileItems/FileItem1", self.FileList),
        self:find("Viewport/Content/FileCont/FileItems/FileItem2", self.FileList),
        self:find("Viewport/Content/FileCont/FileItems/FileItem3", self.FileList),
        self:find("Viewport/Content/FileCont/FileItems/FileItem4", self.FileList),
        self:find("Viewport/Content/FileCont/FileItems/FileItem5", self.FileList),
    }

    self.EditButton = self:find("EditButton", Profile)
    bee.addClick(self.EditButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterChangeName", {data = self._role, from = self.__cname})
    end)

    local Tabs = self:find("Tabs", Profile)
    bee.addValueChanged(self:find("InfoToggle", Tabs), function(isOn)
        if isOn then
            Game:playSound("ui_button_confirm")
            self:showList(1)
        end
    end)
    bee.addValueChanged(self:find("VoiceToggle", Tabs), function(isOn)
        if isOn then
            Game:playSound("ui_button_confirm")
            self:showList(2)
        end
    end)
    bee.addValueChanged(self:find("FileToggle", Tabs), function(isOn)
        if isOn then
            Game:playSound("ui_button_confirm")
            self:showList(3)
        end
    end)

    -- 基础信息映射
    self._baseInfoMap = {
        {self:find("birthday", self.InfoItem1), "birthday"},
        {self:find("height", self.InfoItem1), "height"},
        {self:find("blood", self.InfoItem1), "blood"},
        {self:find("hobby", self.InfoItem1), "hobby"},
        {self:find("star", self.InfoItem1), "star"},
        {self:find("status", self.InfoItem1), "status"},
        {self:find("playstyle", self.InfoItem1), "playstyle"},
    }

    RedManager:bind(self:find("VoiceToggle/Reddot", Tabs), RedTag.CharacterProfileVoices)
    RedManager:bind(self:find("FileToggle/Reddot", Tabs), RedTag.CharacterProfileFiles)
end

function P:onShow()
    P.super.onShow(self)
    self._role = self._params.data or self._datas[1]
    self._introExplsed = true
    self._filesExplsed = true

    self:refreshLeftRight()

    self:refreshUI()
    
    self:playOpenAnim()

    self:profileGuide()
end

function P:refreshUI()
    P.super.refreshUI(self)
    self._init1, self._init2, self._init3 = nil, nil, nil
    self:showList(self._showIndex or 1)
    self:refreshName()
    -- bee.setIcon(self.bg_character_bg_hellhound, "Character[bg_character_bg_camp_" .. self._role.info.campInt .. "]", true)
    local material = ResManager:GetMaterial( "effect/Material/UI/81-90/Mat_UI_88_characterMainProfile_zy0" .. self._role.info.campInt .. ".mat")
    if material then
        self.bg_character_bg_hellhound:GetComponent("Image").material = material
    end
    
    CharacterModel:removeProfileRed(self._role.role_id)
end

function P:showList(index)
    self._showIndex = index
    for k, v in ipairs(self.Views) do
        v:SetActive(k == index)
        -- self.ImageBgs[k]:SetActive(k == index)
    end
    if not self["_init" .. index] then
        self["_init" .. index] = true
        self["initInfo" .. index](self)
    elseif 3 == index then
        self["initInfo" .. index](self)
    end

    if 2 == index then
        CharacterModel:removeVoicetagRed(self._role.role_id)
    elseif 3 == index then
        CharacterModel:removeFiletagRed(self._role.role_id)
    end
    self.EmojiAnim:SetActive(false)
end

function P:initInfo1()
    for _, v in ipairs(self._baseInfoMap) do
        bee.setText(v[1], _T(self._role.info[v[2]]))
    end
    bee.setText(self:find("character_profile_info_frame_02/TIPS", self.InfoItem3), _T(self._role.info.des))

    local emojis = get_tpl_subKey(tpl_emoji_list, "role", self._role.role_id)
    for i = 1, 6 do
        local item = self:find("Emoji" .. i, self.InfoItem2)
        local d = emojis[i]
        if not d then
            item:SetActive(false)
            bee.addClick(item, function()
            end, true)
        else
            item:SetActive(true)
            bee.setIcon(self:find("emoji100101_heart", item), d.emoji)
            self:find("character_profile_emoji_grid_mask", item):SetActive(not d.unlock or d.unlock > self._role:getBondLevel())
            bee.addClick(item, function()
                Game:playSound("ui_button_confirm")
                if not d.unlock or d.unlock > self._role:getBondLevel() then
                    UiManager:showTip({
                        text = d.unlock == (Config.AWAKEN_LEVEL + 1) and _T("LAB_CHAR_106") or _F("LAB_CHAR_105", d.unlock),
                        onSure = function()
                            UiManager:showUI("CharacterMainBonds", {data = self._role, from = "Character"})
                            self:hideUI()
                        end
                    })
                    return
                end
                self.EmojiAnim:SetActive(false)
                self.EmojiAnim:SetActive(true)
                self.EmojiAnim.transform.position = item.transform.position
                bee.setIcon(self:find("Chat_Ani/ImageEmoji/ImageEmoji", self.EmojiAnim), d.emoji)
            end, true)
        end
    end
    bee.addClick(self:find("Title2/TEXT/InfoButton", self.InfoItem2), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonTextTipUD", {text = _T("LAB_CHAR_TIP1"), target = self:find("Title2/TEXT/InfoButton", self.InfoItem2)})
    end)
end

function P:initInfo2()
    if not self.VoiceTree then
        self.VoiceTree = UiTreeEx:create(self.VoiceList)
        self.VoiceTree:setWidth({
            title = 65,
            entry = 90,
        })
        self.VoiceTree:setCreateFunc(function(data)
            if data.__kind == "title" then
                return CU.GameObject.Instantiate(self.VoiceTitle)
            end
            return CU.GameObject.Instantiate(self.VoiceItem1)
        end)
        self.VoiceTree:setRefreshFunc(function(data, item)
            if data.__kind == "title" then
                self:refreshVoiceTitle(data, item)
            else
                self:refreshVoiceEntry(data, item)
            end
        end)
        self._VoiceNodeData = {}
    end
    self._voiceDatas = {
        {tag = CHAT_VOICE_TAG.Login, __kind = "title", name = "LAB_CHAR_033", children = {}, explsed = true}, -- 登录 大厅
        {tag = CHAT_VOICE_TAG.Bond, __kind = "title", name = "LAB_CHAR_034", children = {}}, -- 养成
        {tag = CHAT_VOICE_TAG.Game, __kind = "title", name = "LAB_CHAR_035", children = {}}, -- 对局
        {tag = CHAT_VOICE_TAG.Card, __kind = "title", name = "LAB_CHAR_036", children = {}}, -- 牌型
        {tag = CHAT_VOICE_TAG.Task, __kind = "title", name = "LAB_CHAR_122", children = {}}, -- 任务
    }
    self:_addToVoiceDatas(get_tpl_subKey(tpl_chat_list, "role", self._role.role_id))
    self:_addToVoiceDatas(get_tpl_subKey(tpl_chat_list, "role", 0))
    self.VoiceTree:setDatas(self._voiceDatas)
end

function P:_addToVoiceDatas(datas)
    for _, v in ipairs(datas) do
        local d = self._voiceDatas[v.tag]
        if d then
            table.insert(d.children, {
                __kind = "entry",
                data = v,
            })
        end
    end
end

function P:initInfo3()
    -- 角色介绍
    local IntroCont = self:find("Viewport/Content/IntroCont", self.FileList)
    local IntroTitle = self:find("Title", IntroCont)
    local IntroItems = self:find("IntroItems", IntroCont)
    IntroItems:SetActive(self._introExplsed)
    self:find("arrow02", IntroTitle):SetActive(self._introExplsed ~= true)
    self:find("arrow01", IntroTitle):SetActive(self._introExplsed == true)
    bee.addClick(self:find("Title", IntroCont), function()
        Game:playSound("ui_button_confirm")
        self._introExplsed = not self._introExplsed
        IntroItems:SetActive(self._introExplsed)
        self:find("arrow02", IntroTitle):SetActive(self._introExplsed ~= true)
        self:find("arrow01", IntroTitle):SetActive(self._introExplsed == true)
    end, true)
    bee.addClick(self:find("IntroItem1", IntroItems), function()
        UiManager:showUI("CharacterMainIntroduction", {roleId = self._role.role_id})
    end)

    -- 角色档案
    local FileCont = self:find("Viewport/Content/FileCont", self.FileList)
    local FileTitle = self:find("Title", FileCont)
    local FileItems = self:find("FileItems", FileCont)
    local bonds = get_tpl_subKey(tpl_character_bond_list, "role", self._role.role_id)
    if not bonds or not bonds[1].archive_name then
    --     self.Empty:SetActive(true)
    --     self:find("Viewport", self.FileList):SetActive(false)
    --     self:find("Title", self.FileList):SetActive(false)
        FileCont:SetActive(false)
    else
        FileCont:SetActive(true)
        -- local Title = self:find("Title", self.FileList)
        -- self.Empty:SetActive(false)
        self:find("Viewport", self.FileList):SetActive(self._filesExplsed)
        -- Title:SetActive(true)
        local lvl = self._role:getBondLevel()
        bee.setText(self:find("TextNum", FileTitle), string.format("<color=#5dc4ff>%d</color>/%d", (lvl - 1 > 0) and (lvl - 1) or 0, 5))
        for k, v in ipairs(self.FileItems) do
            local isLock = self._role:getBondLevel() < k + 1
            
            local animator = v:GetComponent("Animator")
            local RedNew = self:find("RedNew", v)
            
            if CharacterModel:isPlayFileAnim(self._role.role_id, k) and not isLock then
                animator.enabled = true
                animator:Play("UI_2_Character_Lock_FileItem")
                self:find("Eff_poker_Ui_profile_js01", v):SetActive(true)
                self:find("character_profile_file_item_off", v):SetActive(true)
                self:find("character_profile_file_item_on", v):SetActive(true)
                RedNew:SetActive(false)
                self:once(0.5, function()
                    RedNew:SetActive(CharacterModel:isNewFilered(self._role.role_id, k))
                end)
            else
                animator.enabled = false
                self:find("Eff_poker_Ui_profile_js01", v):SetActive(false)
                self:find("character_profile_file_item_off", v):SetActive(isLock)
                self:find("character_profile_file_item_on", v):SetActive(not isLock)
                bee.setAlpha(self:find("character_profile_file_item_off", v), 1)
                bee.setAlpha(self:find("character_profile_file_item_on", v), 1)
                RedNew:SetActive(not isLock and CharacterModel:isNewFilered(self._role.role_id, k))
            end

            local name = _T(bonds[k].archive_name)
            bee.setText(self:find("character_profile_file_item_off/TEXT", v), name)
            bee.setText(self:find("character_profile_file_item_on/TEXT", v), name)
            -- self:find("locked", v):SetActive(isLock)
            -- self:find("character_profile_file_play", v):SetActive(not isLock)
            bee.addClick(v, function()
                Game:playSound("ui_button_confirm")
                if isLock then
                    UiManager:showTip({
                        text = k == Config.AWAKEN_LEVEL and _F("LAB_CHAR_108", name) or _F("LAB_CHAR_107", name, k + 1),
                        onSure = function()
                            UiManager:showUI("CharacterMainBonds", {data = self._role, from = "Character"})
                            self:hideUI()
                        end
                    })
                    return
                else
                    UiManager:showUI("CharacterMainProfileDetail", {data = self._role, index = k})
                    bee.logEvent("character-archivesplay", self._role.role_id, k)
                    CharacterModel:removeFilered(self._role.role_id, k)
                    RedNew:SetActive(false)
                end
            end, true)
        end
        self:find("arrow02", FileTitle):SetActive(self._filesExplsed ~= true)
        self:find("arrow01", FileTitle):SetActive(self._filesExplsed == true)
        bee.addClick(FileTitle, function()
            Game:playSound("ui_button_confirm")
            self._filesExplsed = not self._filesExplsed
            FileItems:SetActive(self._filesExplsed)
            self:find("arrow02", FileTitle):SetActive(self._filesExplsed ~= true)
            self:find("arrow01", FileTitle):SetActive(self._filesExplsed == true)
        end, true)
    end
end

function P:refreshName()
    P.super.refreshName(self)
    bee.setText(self.TextName2, self._role:getName())
    local nameCV = "CV:" .. _T(self._role.info.cv)
    bee.setText(self.TextCVInfo, nameCV)
    bee.setText(self.TextCVVoice, nameCV)
    bee.setText(self.TextCVFile, nameCV)
    
    self.EditButton:SetActive(not self._role.locked)
    self:setRoleSound()
end

function P:refreshVoiceTitle(data, item)
    bee.setText(self:find("TextTitle", item), _T(data.name))
    local num, level = 0, self._role:getBondLevel()
    for _, v in ipairs(data.children) do
        if v.data.unlock <= level then
            num = num + 1
        end
    end
    if num < #data.children then
        bee.setText(self:find("TextNum", item), "<color=#c3a9ff>" .. num .. "</color>/" .. #data.children)
    else
        bee.setText(self:find("TextNum", item), "" .. num .. "/" .. #data.children)
    end
    self:find("arrow02", item):SetActive(data.explsed ~= true)
    self:find("arrow01", item):SetActive(data.explsed == true)
    local Reddot = self:find("Reddot", item)
    RedManager:unbind(Reddot)
    RedManager:bind(Reddot, RedTag.CharacterProfileVoices .. data.tag)

    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        self.VoiceTree:setExplsed(data)
        self:find("arrow02", item):SetActive(data.explsed ~= true)
        self:find("arrow01", item):SetActive(data.explsed == true)
    end, true)
end

function P:refreshVoiceEntry(data, item)
    local isLock = data.data.unlock > self._role:getBondLevel()
    self._VoiceNodeData[item] = data

    local animator = item:GetComponent("Animator")
    local RedNew = self:find("RedNew", item)

    if CharacterModel:isPlayVoiceAnim(self._role.role_id, data.data.key) and not isLock then
        self:find("icon_lock_02", item):SetActive(true)
        animator.enabled = true
        animator:Play(0)
        self:find("Eff_poker_Ui_profile_js02", item):SetActive(true)
        self:find("character_profile_voice_item_off", item):SetActive(true)
        self:find("character_profile_voice_item_on", item):SetActive(true)
        RedNew:SetActive(false)
        self:once(0.5, function()
            if self._VoiceNodeData[item] ~= data then
                return
            end
            RedNew:SetActive(CharacterModel:isNewVoicered(self._role.role_id, data.data.key))
        end)
        self:once(2, function()
            if self._VoiceNodeData[item] ~= data then
                return
            end
            animator.enabled = false
            self:find("Eff_poker_Ui_profile_js02", item):SetActive(false)
        end)
    else
        animator.enabled = false
        self:find("Eff_poker_Ui_profile_js02", item):SetActive(false)
        self:find("character_profile_voice_item_off", item):SetActive(isLock)
        self:find("character_profile_voice_item_on", item):SetActive(not isLock)
        bee.setAlpha(self:find("character_profile_voice_item_off", item), 1)
        bee.setAlpha(self:find("character_profile_voice_item_on", item), 1)
        self:find("icon_lock_02", item):SetActive(isLock)
        RedNew:SetActive(not isLock and CharacterModel:isNewVoicered(self._role.role_id, data.data.key))
    end

    bee.setText(self:find("character_profile_voice_item_on/TextName", item), _T(data.data.title))
    bee.setText(self:find("character_profile_voice_item_off/TextName", item), _T(data.data.title))
    self:find("character_profile_voice_play_01", item):SetActive(isLock)
    self:find("character_profile_voice_play_02", item):SetActive(not isLock)
    self:find("character_profile_voice_play", item):SetActive(false)
    if isLock then
        bee.setText(self:find("icon_lock_02/TextLock", item), _T("LAB_CHAR_0" .. (25 + data.data.unlock)))
        bee.setText(self:find("character_profile_voice_item_off/TextName", item), "")
    end

    bee.addClick(item, function()
        if isLock then
            UiManager:showToast(_T("LAB_CHAR_032"))
        else
            self:setRoleSound(item, data)
            bee.logEvent("character-voiceplay", self._role.role_id, data.data.key)
            CharacterModel:removeVoicered(self._role.role_id, data.data.key)
            RedNew:SetActive(false)
        end
    end, true)
end

function P:setRoleSound(item, data)
    Game:stopRoleSound()
    if self._curSoundItem then
        self:find("character_profile_voice_play_01", self._curSoundItem):SetActive(false)
        self:find("character_profile_voice_play_02", self._curSoundItem):SetActive(true)
        self:find("character_profile_voice_play", self._curSoundItem):SetActive(false)
        self._curSoundItem = nil
        if self.FilesTips then
            self.FilesTips:SetActive(false)
        end
    end
    if self._tipTag then
        scheduler:removeTag(self._tipTag)
        self._tipTag = nil
    end
    self._curSoundItem = item
    if item then
        self:find("character_profile_voice_play_01", self._curSoundItem):SetActive(false)
        self:find("character_profile_voice_play_02", self._curSoundItem):SetActive(false)
        self:find("character_profile_voice_play", self._curSoundItem):SetActive(true)

        local dt = 3
        if data.data.tag == CHAT_VOICE_TAG.Game or data.data.tag == CHAT_VOICE_TAG.Card then
            dt = Game:playRoleInVoice(self._role.role_id, data.data.key, true, true)
        else
            dt = Game:playRoleOutVoice(self._role.role_id, data.data.key, true, true)
        end
        if self.FilesTips then
            bee.setText(self:find("TextTip", self.FilesTips), _T(data.data.text))
            self.FilesTips:SetActive(true)
            self._tipTag = self:once(dt, function()
                self.FilesTips:SetActive(false)
                self._tipTag = nil
                self:setRoleSound()
            end)
        end
    end
end

--引导
function P:profileGuide()
    GuideManager:startSystemGuide(6001, 0.65)
end

function P:evt_guide_profile_voice()
    local Tabs = self:find("Profile/Tabs", self.Right)
    local toggle = self:find("VoiceToggle", Tabs):GetComponent("Toggle")
    toggle.isOn = true
    toggle.onValueChanged:Invoke(true)
end

function P:evt_guide_profile_file()
    local Tabs = self:find("Profile/Tabs", self.Right)
    local toggle = self:find("FileToggle", Tabs):GetComponent("Toggle")
    toggle.isOn = true
    toggle.onValueChanged:Invoke(true)
end

