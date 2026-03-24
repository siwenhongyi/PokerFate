local P = class("GMLayer", UiBase)

function P:ctor(params)
    P.super.ctor(self, params)
    self.inPop = true
end

function P:onShow()
    self._gmPos = {1, 5, 9, 6, 3, 5, 7}
    self.Panel = self:find("Panel")
    self.ButtonGM = self:find("ButtonGM")
    self.Panel:SetActive(false)
    self.Poses = {self:find("Pos1"), self:find("Pos2"), self:find("Pos3"), self:find("Pos4"), self:find("Pos5"), self:find("Pos6"), self:find("Pos7"), self:find("Pos8"), self:find("Pos9")}
end

function P:checkClickPos(e)
    local ret, p = CU.RectTransformUtility.ScreenPointToLocalPointInRectangle(self.Panel.transform, e.position, nil)
    -- print(p.x, p.y)
    for k, v in pairs(self.Poses) do
        -- print(v.transform.localPosition, "ggggggggg")
        if math.abs(v.transform.localPosition.x - p.x) <= 150 and math.abs(v.transform.localPosition.y - p.y) <= 150 then
            if 0 == #self._clickPos or self._clickPos[#self._clickPos] ~= k then
                self._clickPos[#self._clickPos + 1] = k
            end
            break
        end
    end
end

function P:onPointerDown(e)
    self._clickPos = {}
    self:checkClickPos(e)
end

function P:onPointerUp(e)
    self:checkClickPos(e)
    
    if #self._clickPos == #self._gmPos then
        local flag = true
        for k, v in ipairs(self._gmPos) do
            if self._clickPos[k] ~= v then
                flag = false
                break
            end
        end
        if flag then
            bee.emit("show_game_debug_button")
        end
    end
    self.ButtonGM:SetActive(true)
    self.Panel:SetActive(false)
end

function P:onBeginDrag(e)
    self:checkClickPos(e)
end

function P:onDrag(e)
    self:checkClickPos(e)
end

function P:onEndDrag(e)
    self:checkClickPos(e)
end

function P:onBtGM()
    if not bee.isRelease then
        bee.emit("show_game_debug_button")
        return
    end
    if self.ButtonGM then
        self.ButtonGM:SetActive(false)
        self.Panel:SetActive(true)
    end
end

function P:onUpdate()
    if bee.isPc and bee.isDev then
        if CU.Input.GetKeyDown(CU.KeyCode.F2) then
            bee.emit("show_game_debug_button")
        elseif CU.Input.GetKeyDown(CU.KeyCode.F3) then
            if bee.checkCd("game_ai_action", 1) then
                bee.emit('game_ai_action')
            end
        end
    end
end

