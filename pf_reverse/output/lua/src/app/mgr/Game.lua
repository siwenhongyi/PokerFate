local P = {}
Game = P

function P:quit()
    if bee.isEditor then
        CS.UnityEditor.EditorApplication.ExitPlaymode()
    else
        CU.Application.Quit()
    end
end

function P:_playSound(key, volume)
    local d = tpl_sound[key]
    if d then
        bee.playSound(d.path, true, volume)
    end
end

function P:playSound(key)
    if self._playingSounds and self._playingSounds[key] then
        return
    end
    local v = SettingModel:getSoundVolume()
    if v > 0 then
        self:_playSound(key, v)
        if not self._playingSounds then
            self._playingSounds = {}
        end
        self._playingSounds[key] = true
    end
end

-- 播放角色局内语音
function P:playRoleInVoice(role_id, key, isReturnTime, force)
    local v = SettingModel:getRoleInVolume(role_id)
    if v <= 0 and force then v = 1 end
    if v > 0 then
        bee.playVoice("sound/" .. role_id .. "/" .. key .. ".wav", true, v)
        bee.setMixerVolume("volumeMusic", -6)
        self.volumeMusic = -6
        self._isVoicePlaying = 1
        if isReturnTime then
            local audio = ResManager:GetSound("sound/" .. role_id .. "/" .. key .. ".wav")
            if audio then
                return audio.length
            end
        end
    end
    return 3
end

-- 播放角色局外语音
function P:playRoleOutVoice(role_id, key, isReturnTime, force)
    if not role_id then
        role_id = CharacterModel:getUsingRoleId()
    end
    local v = SettingModel:getRoleOutVolume(role_id)
    if v <= 0 and force then v = 1 end
    if v > 0 then
        bee.playVoice("sound/" .. role_id .. "/" .. key .. ".wav", true, v)
        bee.setMixerVolume("volumeMusic", -6)
        self.volumeMusic = -6
        self._isVoicePlaying = 1
        if isReturnTime then
            local audio = ResManager:GetSound("sound/" .. role_id .. "/" .. key .. ".wav")
            if audio then
                return audio.length
            end
        end
    end
    return 3
end

function P:stopRoleSound()
    bee.stopVoice()
    bee.setMixerVolume("volumeMusic", 0)
    self.volumeMusic = 0
    self._isVoicePlaying = nil
end

function P:playStoryVoice(voice)
    bee.setMixerVolume("volumeMusic", -6)
    return bee.playSound(voice, true)
end

function P:stopStoryVoice()
    bee.stopSound("")
    bee.setMixerVolume("volumeMusic", 0)
end

function P:playMusic(key, volume)
    if self._fadeInTween then
        self._fadeInTween:Kill()
        self._fadeInTween = nil
    end
    if self._fadeOutTween then
        self._fadeOutTween:Kill()
        self._fadeOutTween = nil
    end
    local isFirst
    if not self._music then
        isFirst = true
    end
    if self._music ~= key then
        self._music = key
        local d = tpl_sound[tostring(key)]
        if d then
            bee.playMusic(d.path, true, volume)
            if d.loop_start then
                CS.SoundManager.Instance:SetMusicLoopTime(d.loop_start)
            end
            if self._time then
                self._length = ResManager:GetSound(d.path).length
            end

            if not isFirst then
                -- 切换bgm时淡入效果
                self._fadeInTween = bee.Tween.toFloat(0, 1, 5, function(v)
                    bee.changeMusicVolume(v * volume)
                    if v >= 1 then
                        self._fadeInTween = nil
                    end
                end)
            end
        end
    end
end

function P:stopMusic()
    self._music = nil
    self._time = nil
    self._length = nil
    self._lobbyBgmList = nil
    self._lobbyBgmIndex = nil
    if self._fadeInTween then
        self._fadeInTween:Kill()
        self._fadeInTween = nil
    end
    if self._fadeOutTween then
        self._fadeOutTween:Kill()
        self._fadeOutTween = nil
    end
    bee.stopMusic()
end

function P:playLobbyBGM()
    self:stopMusic()

    local v = SettingModel:getLobbyBGMVolume()
    if v > 0 then
        self._lobbyBgmList = PlayerModel:getCurMusicLobby()
        self._lobbyBgmCount = #self._lobbyBgmList
        self._lobbyBgmIndex = nil
        self:switchLobbyBGM()
    end
end

function P:switchLobbyBGM()
    if not self._lobbyBgmList then
        return
    end
    if self._lobbyBgmCount > 1 then
        self._time = 0
        self._length = 0
    end
    if PlayerModel:getLobbyMusicTag() == MusicTag.Order then
        if self._lobbyBgmIndex then
            self._lobbyBgmIndex = self._lobbyBgmIndex + 1
            if self._lobbyBgmIndex > self._lobbyBgmCount then
                self._lobbyBgmIndex = 1
            end
        else
            self._lobbyBgmIndex = 1
        end
        self:playMusic(self._lobbyBgmList[self._lobbyBgmIndex], SettingModel:getLobbyBGMVolume())
    else
        local rand = math.random(#self._lobbyBgmList)
        self:playMusic(self._lobbyBgmList[rand], SettingModel:getLobbyBGMVolume())
    end
end

function P:playGachaMusic()
    self:stopMusic()
    local v = SettingModel:getLobbyBGMVolume()
    if v > 0 then
        self:playMusic("cacha001", v)
    else
        self:stopMusic()
    end
end

function P:playIngameBGM()
    self:stopMusic()
    local v = SettingModel:getIngameBGMVolume()
    if v > 0 then
        self:playMusic(PlayerModel:getCurMusicBattle(), v)
    else
        self:stopMusic()
    end
end

function P:start()
    bee.addUpdater(function(dt)
        self:onUpdate(dt)
    end)
end

function P:onUpdate(dt)
    if self._playingSounds then
        self._playingSounds = nil
    end
    if self._isVoicePlaying then
        self._isVoicePlaying = self._isVoicePlaying - dt
        if self._isVoicePlaying <= 0 and not CS.SoundManager.Instance:IsVoicePlaying() then
            self._isVoicePlaying = nil
            bee.setMixerVolume("volumeMusic", 0)
        end
    end

    if self._time then
        self._time = self._time + dt
        if self._time > self._length then
            self:switchLobbyBGM()
        end
        -- bgm淡出效果
        if (self._length - self._time) < 5 then
            if not self._fadeOutTween then
                self._fadeOutTween = bee.Tween.toFloat(1, 0, 5, function(v)
                    bee.changeMusicVolume(v * SettingModel:getLobbyBGMVolume())
                end)
            end
        end
    end
end

-- 继续播放大厅音乐（淡入）
function P:playLobbyMusicTween()
    if self._fadeInTween then
        self._fadeInTween:Kill()
        self._fadeInTween = nil
    end
    if self._fadeOutTween then
        self._fadeOutTween:Kill()
        self._fadeOutTween = nil
    end

    CS.SoundManager.Instance:UnPauseMusic()
    self._fadeInTween = bee.Tween.toFloat(0, 1, 5, function(v)
        bee.changeMusicVolume(v * SettingModel:getLobbyBGMVolume())
        if v >= 1 then
            self._fadeInTween = nil
        end
    end)
end

-- 暂停大厅音乐（淡出）
function P:pauseLobbyMusicTween()
    if self._fadeInTween then
        self._fadeInTween:Kill()
        self._fadeInTween = nil
    end
    if self._fadeOutTween then
        self._fadeOutTween:Kill()
        self._fadeOutTween = nil
    end
    self._fadeOutTween = bee.Tween.toFloat(1, 0, 5, function(v)
        bee.changeMusicVolume(v * SettingModel:getLobbyBGMVolume())
        if v <= 0 then
            CS.SoundManager.Instance:PauseMusic()
        end
    end)
end

