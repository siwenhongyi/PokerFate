local P = class("GalaSeasonPlayer", UiDialog)

function P:onAwake()
    self._isMute = true
    self.Center = self:find("AnimRoot/Center")
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.title_limited = self:find("title_limited", self.Panel)
    self.ChooseButton = self:find("ChooseButton", self.Panel)
    self.GoButton = self:find("GoButton", self.Panel)
    self.UsingButton = self:find("UsingButton", self.Panel)

    self.PiyoList = self:find("PiyoList", self.Panel)
    self.PiyoView = self:find("PiyoView", self.Panel)
    self.Item = self:find("Item1", self.PiyoList)
    self.Item:SetActive(false)

    bee.addClick(self:find("Popup/GalaSeason_btn_tc_close", self.Panel), function()
        self:hideUI()
    end)

    bee.addClick(self.ChooseButton, function()
        Game:playSound("ui_button_confirm")
        if bee.checkCd("GalaSeasonPlayer_ChooseButton", 2) then
            ThemeModel:reqSetCurRole(self._selectedId)
            if GAME_GAME_TYPE.TOURNAMENT == GameModel.selectRoomGameType then
                bee.logEvent("galaseason_tournament_select_use", self._selectedId)
            else
                bee.logEvent("galaseason_select_use", GameModel.selectRoomGameType, self._selectedId)
            end
        end
    end)

    bee.addClick(self.GoButton, function()
        Game:playSound("ui_button_confirm")
        local d = tpl_character[ self._selectedId ]
        if d then
            ItemModel:jumpView(d.accesses[1])
            if GAME_GAME_TYPE.TOURNAMENT == GameModel.selectRoomGameType then
                bee.logEvent("galaseason_tournament_select_link", self._selectedId)
            else
                bee.logEvent("galaseason_select_link", GameModel.selectRoomGameType, self._selectedId)
            end
        end
    end)
end

function P:onShow()
    local data = tpl_theme_activity[ThemeModel:getConfId()]
    if GAME_GAME_TYPE.TOURNAMENT == GameModel.selectRoomGameType then
        bee.logEvent("galaseason_tournament_select")
    else
        bee.logEvent("galaseason_select", GameModel.selectRoomGameType)
    end

    self._selectedItem = nil
    self._selectedId = nil
    self._Items = {}
    self._datas = {}

    local count = #data.player_add / 2
    local View = self.PiyoView
    if count > 4 then
        View = self:find("Viewport/Content", self.PiyoList)
    else
    end
    self:removeAllChildren(View)
    for i = 1, #data.player_add - 1, 2 do
        local item = CU.GameObject.Instantiate(self.Item, View.transform, false)
        item:SetActive(true)
        self._Items[#self._Items + 1] = item
        self._datas[#self._datas + 1] = {role_id = data.player_add[i], add = data.player_add[i + 1]}
        self:refreshItem(self._datas[#self._datas], item)
        if data.player_add[i] == ThemeModel:getCurRoleId() then
            self:refreshSelected(item, data.player_add[i])
        end
    end
    if not self._selectedItem then
        self:refreshSelected(self._Items[1], data.player_add[1])
    end
end

function P:refreshItem(data, item)
    bee.setTextCut(self:find("TextName", item), CharacterModel:getRoleName(data.role_id), 160)
    
    local skin = CharacterModel:getRoleSkinData(data.role_id)
    bee.setIcon(self:find("ImageIcon", item), skin.ui_avatar_1)
    self:find("GalaSeason_player_frame_chose_01", item):SetActive(false)

    local isLock = CharacterModel:getRole(data.role_id) == nil
    bee.setGrey(self:find("ImageIcon", item), isLock)
    
    self:find("GalaSeason_player_frame_chose_02", item):SetActive(not isLock and data.role_id == ThemeModel:getCurRoleId())
    self:find("GalaSeason_player_frame_chose_03", item):SetActive(not isLock and data.role_id ~= ThemeModel:getCurRoleId())
    self:find("GalaSeason_player_frame_chose_04", item):SetActive(isLock)

    bee.setText(self:find("Point/Text", item), "+" .. data.add / 10 .. "%")

    bee.addClick(item, function()
        self:refreshSelected(item, data.role_id)
    end)
end

function P:refreshSelected(item, id, force)
    if item == self._selectedItem and not force then
        return
    end
    if self._selectedItem then
        self:find("GalaSeason_player_frame_chose_01", self._selectedItem):SetActive(false)
    end
    self._selectedItem = item
    self._selectedId = id
    self:find("GalaSeason_player_frame_chose_01", item):SetActive(true)

    -- self.title_limited = self:find("title_limited", self.Center)
    -- self.ChooseButton = self:find("ChooseButton", self.Center)
    -- self.GoButton = self:find("GoButton", self.Center)
    -- self.UsingButton = self:find("UsingButton", self.Center)

    if id == ThemeModel:getCurRoleId() then
        self.title_limited:SetActive(false)
        self.ChooseButton:SetActive(false)
        self.GoButton:SetActive(false)
        self.UsingButton:SetActive(true)
    else
        local r = CharacterModel:getRole(id)
        if r and not r.locked then
            self.title_limited:SetActive(false)
            self.ChooseButton:SetActive(true)
            self.GoButton:SetActive(false)
            self.UsingButton:SetActive(false)
        elseif ItemModel:isCanJump(tpl_character[id].accesses, id) then
            self.title_limited:SetActive(false)
            self.ChooseButton:SetActive(false)
            self.GoButton:SetActive(true)
            self.UsingButton:SetActive(false)
        else
            self.title_limited:SetActive(true)
            self.ChooseButton:SetActive(false)
            self.GoButton:SetActive(false)
            self.UsingButton:SetActive(false)
        end
    end
end

function P:evt_updateScheme()
    self:hideUI()
end

function P:evt_RoleUnlockRSP()
    for k, v in ipairs(self._Items) do
        self:refreshItem(self._datas[k], v)
    end
    self:refreshSelected(self._selectedItem, self._selectedId, true)
end

