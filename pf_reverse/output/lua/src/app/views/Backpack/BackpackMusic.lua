local P = class("BackpackMusic", UiDialog)

--[[ 参数
    {data = 当前播放数据, list = 播放列表, cb = 选中回调(data)}
]]
function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    local Center = self:find("AnimRoot/Center")

    self.TextTimeStart = self:find("TextTimeStart", Center)
    self.TextTimeEnd = self:find("TextTimeEnd", Center)
    self.TextScrollView = self:find("TextScrollView", Center)
    self.TextDec = self:find("TextScrollView/Viewport/Content/TextDec", Center)
    self.TextName = self:find("TextName", Center)

    self.PlayButton = self:find("PlayButton", Center)
    self.PauseButton = self:find("PauseButton", Center)
    self.CycleSingleButton = self:find("CycleSingleButton", Center)
    self.CycleListButton = self:find("CycleListButton", Center)
    self.CycleRandomButton = self:find("CycleRandomButton", Center)
    self.LastButton = self:find("LastButton", Center)
    self.NextButton = self:find("NextButton", Center)
    self.ListButton = self:find("ListButton", Center)

    self.MusicList = self:find("MusicList", Center)
    self.Item1 = self:find("Item1", self.MusicList)
    self.Item1:SetActive(false)
    self.MusicSlider = self:find("MusicSlider", Center)

    self.BgPoint = self:find("BgPoint", Center)
    self.bg_backpack_music_01 = self:find("bg_backpack_music_01", Center)

    self.ThemeTag = self:find("ThemeTag", Center)
    self.DiscountText = self:find("Discount/DiscountText", self.ThemeTag)
    self.OwnedButton = self:find("OwnedButton", Center)
    self.PurchaseButton = self:find("PurchaseButton", Center)
    self.PriText = self:find("PriText", self.PurchaseButton)
    self.PriIcon = self:find("PriIcon", self.PurchaseButton)

    bee.addClick(self:find("CloseButton", Center), function()
        if self._isPlaying then
            bee.stopSoundByIndex(self._playIndex)
        end
        Game:resumeBGM()
        self:hideUI()
    end)
    bee.addClick2(self:find("common_panel_mask_70", AnimRoot), function()
        if self._isPlaying then
            bee.stopSoundByIndex(self._playIndex)
        end
        Game:resumeBGM()
        self:hideUI()
    end)

    bee.addClick(self.PlayButton, function()
        Game:playSound("ui_button_confirm")
        self:onBtPlay()
    end)
    bee.addClick(self.PauseButton, function()
        Game:playSound("ui_button_confirm")
        self:onBtStop()
    end)

    bee.addClick(self.LastButton, function()
        Game:playSound("ui_button_confirm")
        local index = 1
        for k, v in ipairs(self._list) do
            if self._data == v then
                index = k - 1
                break
            end
        end
        if index < 1 then
            index = #self._list
        end
        self:setCurData(self._list[index])
        self.ListMusic:refreshShowingUi()
        bee.stopSoundByIndex(self._playIndex)
        self:playMusic()
    end)
    bee.addClick(self.NextButton, function()
        Game:playSound("ui_button_confirm")
        local index = 1
        for k, v in ipairs(self._list) do
            if self._data == v then
                index = k + 1
                break
            end
        end
        if index > #self._list then
            index = 1
        end
        self:setCurData(self._list[index])
        self.ListMusic:refreshShowingUi()
        bee.stopSoundByIndex(self._playIndex)
        self:playMusic()
    end)
    bee.addClick(self.ListButton, function()
        Game:playSound("ui_button_confirm")
        self.MusicList:SetActive(not self.MusicList.activeSelf)
        self.TextScrollView:SetActive(not self.MusicList.activeSelf)
    end)

    bee.addClick(self.CycleSingleButton, function()
        Game:playSound("ui_button_confirm")
        self._cycleType, self._randomList = 2, nil
        self:refreshCycle()
    end)
    bee.addClick(self.CycleListButton, function()
        Game:playSound("ui_button_confirm")
        self._cycleType, self._randomList = 3, nil
        self:refreshCycle()
    end)
    bee.addClick(self.CycleRandomButton, function()
        Game:playSound("ui_button_confirm")
        self._cycleType, self._randomList = 1, nil
        self:refreshCycle()
    end)
    bee.addClick(self.ThemeTag, function()
        Game:playSound("ui_button_confirm")
        local shopCfg = ShopModel:getDecorateShopCfgById(self._data.item_id)
        bee.logEvent("shop-music-link", shopCfg.id)
        local themeId = ShopModel:getItemIsInThemePackage(self._data.item_id)
        if themeId then
            ItemModel:jumpView(106001, themeId)
        end
        if self._isPlaying then
            bee.stopSoundByIndex(self._playIndex)
        end
        Game:resumeBGM()
        self:hideUI()
    end)

    self.ListMusic = UiListEx:create(self.MusicList)
    self.ListMusic:setWidth(74)
    self.ListMusic:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListMusic:setRefreshFunc(function(data, item)
        self:refreshItem(data, item)
    end)

    bee.addValueChanged(self.MusicSlider, function(val)
        if not self._modSlider and self._playIndex then
            self._time = val * self._length
            CS.SoundManager.Instance:SetSoundTime(self._playIndex, self._time)
        end
    end, "Slider")

    bee.addClick(self.PurchaseButton, function()
        Game:playSound("ui_button_confirm")
        local shopCfg = ShopModel:getDecorateShopCfgById(self._data.item_id)
        bee.logEvent("shop-music-buy", shopCfg.id)
        UiManager:showUI("ShopExchangeSingle", {data = {cfg = shopCfg}})
    end)
    bee.addClick(self.OwnedButton, function()
        UiManager:showToast(_T("TAB_SHOP_THEME_11"))
    end)

    Game:pauseBGM()
end

function P:onShow()
    self._list = self._params.list
    if not self._list then
        self._list = {self._params.data}
    end

    if self._params.selectList then
        self._selectedList = {}
        for k,v in pairs(self._params.selectList) do
            self._selectedList[k] = v
        end
    end
    if self._params.cycleType then
        self._cycleType = self._params.cycleType
    else
        self._cycleType = 1
    end
    
    self._randomList = nil
    self:setCurData(self._params.data)
    self.ListMusic:setDatas(self._list)
    self:refreshCycle()
    self:once(0.5, function()
        self:playMusic()
    end)
end

function P:preHide()
    P.super.preHide(self)
    if self._params.cb then
        self._params.cb(self._data)
    end
end

function P:onBtClose()
    if self._isPlaying then
        bee.stopSoundByIndex(self._playIndex)
    end
    Game:resumeBGM()
    P.super.onBtClose(self)
end

function P:_stopAct()
    if self._ratateAct then
        self._ratateAct:kill()
        self._ratateAct = nil
    end
    if self._loopAct then
        self._loopAct:kill()
        self._loopAct = nil
    end
end

function P:startToPlay()
    self:_stopAct()
    self._ratateAct = bee.tween(self.BgPoint)
    : to(0.5, {rotate = bee.v3(0, 0, -8)})
    : onComplete(function()
        self._ratateAct = nil
        self._loopAct = bee.tween(self.bg_backpack_music_01)
        : by(30, {rotate = bee.v3(0, 0, -360)}, {rotate = DT.RotateMode.FastBeyond360})
        : ease(DT.Ease.Linear)
        : loop(-1)
        : link()
    end)
    : link()
end

function P:stopToPlay()
    self:_stopAct()
    self._ratateAct = bee.tween(self.BgPoint)
    : to(0.5, {rotate = bee.v3(0, 0, 0)})
    : onComplete(function()
        self._ratateAct = nil
    end)
    : link()
end

function P:evt_ItemChangeRSP()
    self:refreshShopInfo()
    self:refreshItem(self._data, self.ListMusic:getDataNode(self._data))
end

function P:refreshShopInfo()
    local isOwn = ItemModel:getItem(self._data.item_id)
    if not isOwn then
        local themeId = ShopModel:getItemIsInThemePackage(self._data.item_id)
        if themeId and ShopModel:getThemeIsCanBuy(themeId) then
            self.ThemeTag:SetActive(true)
            local themeCfg = tpl_shop_theme[themeId]
            bee.setText(self.DiscountText, ((1000 - themeCfg.discount) / 10) .. "%")
        else
            self.ThemeTag:SetActive(false)
        end
    else
        self.ThemeTag:SetActive(false)
    end

    if self._params.isShop then
        if not isOwn then
            local shopCfg = ShopModel:getDecorateShopCfgById(self._data.item_id)
            if shopCfg then
                self.PurchaseButton:SetActive(true)
                self.OwnedButton:SetActive(false)
                bee.setIconInAtlas(self.PriIcon, tpl_props[shopCfg.pri[1]].icon)
                bee.setText(self.PriText, shopCfg.pri[2])
            else
                self.PurchaseButton:SetActive(false)
                self.OwnedButton:SetActive(false)
            end
        else
            self.PurchaseButton:SetActive(false)
            self.OwnedButton:SetActive(true)
        end
    else
        self.PurchaseButton:SetActive(false)
        self.OwnedButton:SetActive(false)
    end
end

function P:setCurData(data)
    if self._data == data then return end
    self._data = data
    local d = tpl_props[self._data.item_id]

    bee.setText(self.TextName, _T(d.name))
    bee.setText(self.TextDec, _T(d.des))
    local sound = tpl_sound[tostring(d.mapId)]
    self._length = 0
    self._path = ""
    self._isPlaying = false
    self._time = 0

    if sound then
        self.audio = ResManager:GetSound(sound.path)
        self._path = sound.path
    else
        self.audio = nil
    end
    if self.audio then
        self._length = self.audio.length
    end
    bee.setText(self.TextTimeStart, self:getTimeStr(self._time))
    bee.setText(self.TextTimeEnd, self:getTimeStr(self._length))
    bee.setSliderValue(self.MusicSlider, 0)
    if sound.cd_image then
        bee.setIcon(self.bg_backpack_music_01, sound.cd_image)
        self.bg_backpack_music_01.transform.localEulerAngles = bee.v3(0, 0, 0)
    end

    self.PlayButton:SetActive(true)
    self.PauseButton:SetActive(false)

    self.MusicList:SetActive(false)
    self.TextScrollView:SetActive(not self.MusicList.activeSelf)

    self:refreshShopInfo()
end

function P:refreshItem(data, item)
    if not item then return end
    local d = tpl_props[data.item_id]
    
    if self._data == data or (self._data.item_id and self._data.item_id == data.item_id) then
        self:find("backpack_music_list_item_playing", item):SetActive(true)
        self:find("TextName1", item):SetActive(true)
        self:find("TextName2", item):SetActive(false)
        bee.setText(self:find("TextName1", item), _T(d.name))
    else
        self:find("backpack_music_list_item_playing", item):SetActive(false)
        self:find("TextName1", item):SetActive(false)
        self:find("TextName2", item):SetActive(true)
        bee.setText(self:find("TextName2", item), _T(d.name))
    end

    local Lock1 = self:find("Lock1", item)
    local Lock2 = self:find("Lock2", item)
    if ItemModel:getItem(data.item_id) then
        Lock1:SetActive(false)
        Lock2:SetActive(false)
    else
        if ShopModel:getItemIsInThemePackage(data.item_id) then
            Lock1:SetActive(false)
            Lock2:SetActive(true)
        else
            Lock1:SetActive(true)
            Lock2:SetActive(false)
        end
    end

    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        if self._data ~= data then
            local oldData = self._data
            self:setCurData(data)
            self:refreshItem(data, item)
            if oldData then
                self:refreshItem(oldData, self.ListMusic:getDataNode(oldData))
            end
            bee.stopSoundByIndex(self._playIndex)
            self:playMusic()
        end
    end)

    local SelectToggle = self:find("SelectToggle", item)
    if self._selectedList then
        SelectToggle:SetActive(true)
        if self._selectedList[d.id] then
            bee.setCheck(SelectToggle)
        else
            bee.setUncheck(SelectToggle)
        end
    else
        SelectToggle:SetActive(false)
    end
    bee.addValueChanged(SelectToggle, function(isOn)
        if isOn then
            self._selectedList[d.id] = true
        else
            local tag = false
            for k, v in pairs(self._selectedList) do
                if k ~= d.id and v then
                    tag = true
                    break
                end
            end
            if not tag then
                UiManager:showToast(_T("LAB_CUSTOM_19"))
                bee.setCheck(SelectToggle)
            else
                self._selectedList[d.id] = false
            end
        end
    end)
end

function P:refreshCycle()
    self.CycleSingleButton:SetActive(self._cycleType == 1)
    self.CycleListButton:SetActive(self._cycleType == 2)
    self.CycleRandomButton:SetActive(self._cycleType == 3)
end

function P:playMusic()
    if self.audio then
        if not self._isPlaying then
            self:startToPlay()
        end
        self.PlayButton:SetActive(false)
        self.PauseButton:SetActive(true)
        self._isPlaying = true
        self._time = 0
        bee.stopSoundByIndex(self._playIndex)
        self._playIndex = bee.playSound(self._path)
    end
end

function P:onBtPlay()
    if self.audio then
        if not self._isPlaying then
            self:startToPlay()
        end
        self._isPlaying = true
        self.PlayButton:SetActive(false)
        self.PauseButton:SetActive(true)
        bee.unPauseSound(self._playIndex)
    end
end

function P:onBtStop()
    if self.audio then
        if self._isPlaying then
            self:stopToPlay()
        end
        self.PlayButton:SetActive(true)
        self.PauseButton:SetActive(false)
        self._isPlaying = false
        bee.pauseSound(self._playIndex)
    end
end

function P:getTimeStr(dt)
    dt = math.ceil(dt)
    return string.format("%02d:%02d", math.floor(dt / 60), dt % 60)
end

function P:refreshSlider()
    self._modSlider = true
    if self._length > 0 then
        bee.setSliderValue(self.MusicSlider, self._time > self._length and 1 or (self._time / self._length))
    else
        bee.setSliderValue(self.MusicSlider, 0)
    end
    self._modSlider = nil
end

function P:onUpdate(dt)
    if self._isPlaying then
        self._time = self._time + dt
        if self._length > 0 then
            self:refreshSlider()
        end
        if self._time >= self._length then
            self._time = 0
            if self._cycleType == 1 then
            elseif self._cycleType == 2 then
                local index = 1
                for k, v in ipairs(self._list) do
                    if v == self._data then
                        index = k
                        break
                    end
                end
                index = index + 1
                if index > #self._list then
                    index = 1
                end
                self:setCurData(self._list[index])
                self.ListMusic:refreshShowingUi()
            elseif self._cycleType == 3 then
                if not self._randomList or #self._randomList == 0 then
                    self._randomList = {}
                    for k, v in ipairs(self._list) do
                        if v ~= self._data then
                            table.insert(self._randomList, v)
                        end
                    end
                    if #self._randomList > 0 then
                        local index = math.random(#self._randomList)
                        self:setCurData(self._list[index])
                        self.ListMusic:refreshShowingUi()
                        table.remove(self._randomList, index)
                    end
                end
            end
            self:playMusic()
        end
        bee.setText(self.TextTimeStart, self:getTimeStr(self._time))
    end
end

return P